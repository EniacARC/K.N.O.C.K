import socket
import threading
import time
import hashlib
import random
import logging
import struct
from sip_msgs import SIPMsgFactory, SIPMethod, SIPStatusCode, SIPRequest, SIPResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sip_server')


class RTPPacket:
    """RTP packet parser and builder"""

    def __init__(self, version=2, padding=0, extension=0, cc=0, marker=0,
                 payload_type=0, sequence=0, timestamp=0, ssrc=0, payload=b''):
        self.version = version  # 2 bits
        self.padding = padding  # 1 bit
        self.extension = extension  # 1 bit
        self.cc = cc  # 4 bits (CSRC count)
        self.marker = marker  # 1 bit
        self.payload_type = payload_type  # 7 bits
        self.sequence = sequence  # 16 bits
        self.timestamp = timestamp  # 32 bits
        self.ssrc = ssrc  # 32 bits
        self.csrc = []  # list of 32-bit CSRC items
        self.payload = payload  # variable length

    @classmethod
    def parse(cls, data):
        """Parse an RTP packet from bytes"""
        if len(data) < 12:  # Minimum RTP header size
            return None

        # Parse the first byte
        first_byte = data[0]
        version = (first_byte >> 6) & 0x03
        padding = (first_byte >> 5) & 0x01
        extension = (first_byte >> 4) & 0x01
        cc = first_byte & 0x0F

        # Parse the second byte
        second_byte = data[1]
        marker = (second_byte >> 7) & 0x01
        payload_type = second_byte & 0x7F

        # Parse sequence number (16 bits)
        sequence = struct.unpack('!H', data[2:4])[0]

        # Parse timestamp (32 bits)
        timestamp = struct.unpack('!I', data[4:8])[0]

        # Parse SSRC (32 bits)
        ssrc = struct.unpack('!I', data[8:12])[0]

        # Create packet instance
        packet = cls(version, padding, extension, cc, marker,
                     payload_type, sequence, timestamp, ssrc)

        # Parse CSRC list if any
        offset = 12
        for i in range(cc):
            if offset + 4 <= len(data):
                packet.csrc.append(struct.unpack('!I', data[offset:offset + 4])[0])
                offset += 4

        # Extract payload
        packet.payload = data[offset:]

        return packet

    def build(self):
        """Convert the RTP packet to bytes"""
        # First byte: V=2, P, X, CC
        first_byte = ((self.version & 0x03) << 6) | \
                     ((self.padding & 0x01) << 5) | \
                     ((self.extension & 0x01) << 4) | \
                     (self.cc & 0x0F)

        # Second byte: M, PT
        second_byte = ((self.marker & 0x01) << 7) | \
                      (self.payload_type & 0x7F)

        # Build the header
        header = bytearray([first_byte, second_byte])

        # Add sequence number (16 bits)
        header.extend(struct.pack('!H', self.sequence & 0xFFFF))

        # Add timestamp (32 bits)
        header.extend(struct.pack('!I', self.timestamp & 0xFFFFFFFF))

        # Add SSRC (32 bits)
        header.extend(struct.pack('!I', self.ssrc & 0xFFFFFFFF))

        # Add CSRC list if any
        for csrc in self.csrc[:self.cc]:
            header.extend(struct.pack('!I', csrc & 0xFFFFFFFF))

        # Add payload
        result = bytes(header) + self.payload
        return result

    def __str__(self):
        return (f"RTP: V={self.version}, P={self.padding}, X={self.extension}, CC={self.cc}, "
                f"M={self.marker}, PT={self.payload_type}, Seq={self.sequence}, "
                f"TS={self.timestamp}, SSRC={self.ssrc}, Payload={len(self.payload)} bytes")


class RTPSession:
    """Represents an RTP session between two endpoints"""

    def __init__(self, call_id, from_endpoint, to_endpoint):
        self.call_id = call_id
        self.from_endpoint = from_endpoint
        self.to_endpoint = to_endpoint
        self.from_rtp_port = None
        self.to_rtp_port = None
        self.from_rtcp_port = None
        self.to_rtcp_port = None
        self.from_last_seq = 0
        self.to_last_seq = 0
        self.active = False
        self.start_time = None
        self.end_time = None
        self.packets_from_to = 0
        self.packets_to_from = 0
        self.bytes_from_to = 0
        self.bytes_to_from = 0
        self.codec = None

    def start(self):
        """Start the RTP session"""
        self.active = True
        self.start_time = time.time()

    def stop(self):
        """Stop the RTP session"""
        self.active = False
        self.end_time = time.time()

    def get_duration(self):
        """Get the duration of the RTP session"""
        if self.start_time:
            if self.end_time:
                return self.end_time - self.start_time
            else:
                return time.time() - self.start_time
        return 0

    def get_stats(self):
        """Get statistics about the RTP session"""
        return {
            'call_id': self.call_id,
            'from': self.from_endpoint.uri,
            'to': self.to_endpoint.uri,
            'active': self.active,
            'duration': self.get_duration(),
            'packets_from_to': self.packets_from_to,
            'packets_to_from': self.packets_to_from,
            'bytes_from_to': self.bytes_from_to,
            'bytes_to_from': self.bytes_to_from,
            'codec': self.codec
        }


class SIPEndpoint:
    def __init__(self, uri, ip, port, expires=3600):
        self.uri = uri
        self.ip = ip
        self.port = port
        self.expires = expires
        self.last_seen = time.time()
        self.calls = set()  # Store active call IDs
        self.rtp_port = None
        self.rtcp_port = None

    def is_expired(self):
        return time.time() > (self.last_seen + self.expires)

    def update_registration(self, ip, port, expires=3600):
        self.ip = ip
        self.port = port
        self.expires = expires
        self.last_seen = time.time()

    def __str__(self):
        return f"Endpoint: {self.uri} @ {self.ip}:{self.port}, expires in {int(self.last_seen + self.expires - time.time())}s"


class AuthChallenge:
    def __init__(self, uri, nonce, realm="sipserver"):
        self.uri = uri
        self.nonce = nonce
        self.realm = realm
        self.created_at = time.time()

    def is_expired(self):
        # Challenges expire after 5 minutes
        return time.time() > (self.created_at + 300)


class SIPCall:
    def __init__(self, call_id, from_uri, to_uri):
        self.call_id = call_id
        self.from_uri = from_uri
        self.to_uri = to_uri
        self.established = False
        self.start_time = None
        self.end_time = None
        self.rtp_session = None
        self.sdp_from = None  # SDP from the caller
        self.sdp_to = None  # SDP from the callee

    def establish(self):
        self.established = True
        self.start_time = time.time()

    def terminate(self):
        self.established = False
        self.end_time = time.time()
        if self.rtp_session:
            self.rtp_session.stop()

    def get_duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0


class SIPServer:
    def __init__(self, host='0.0.0.0', port=5060, rtp_port_range=(10000, 20000), auth_required=True):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.endpoints = {}  # uri -> SIPEndpoint
        self.auth_challenges = {}  # uri -> AuthChallenge
        self.calls = {}  # call_id -> SIPCall
        self.auth_required = auth_required
        self.credentials = {}  # uri -> password hash (SHA-256)
        self.lock = threading.RLock()

        # RTP related
        self.rtp_port_range = rtp_port_range
        self.rtp_sessions = {}  # call_id -> RTPSession
        self.rtp_ports_in_use = set()
        self.rtp_socket = None
        self.rtp_threads = {}  # port -> thread

        # Load credentials - in a real system, this would be from a database
        self._load_credentials()

    def _load_credentials(self):
        # This is a simple example - in a real-world scenario, these would come from a database
        example_creds = {
            "alice": "password123",
            "bob": "securepass",
            "carol": "test1234"
        }

        for username, password in example_creds.items():
            uri = f"{username}@sipserver"
            self.credentials[uri] = hashlib.sha256(password.encode()).hexdigest()
            logger.info(f"Loaded credentials for {uri}")

    def _get_free_rtp_port(self):
        """Find and reserve a free RTP port"""
        with self.lock:
            for port in range(self.rtp_port_range[0], self.rtp_port_range[1], 2):  # RTP uses even ports
                if port not in self.rtp_ports_in_use:
                    # Reserve both RTP port and the next odd port for RTCP
                    self.rtp_ports_in_use.add(port)
                    self.rtp_ports_in_use.add(port + 1)
                    return port
            return None

    def _release_rtp_port(self, port):
        """Release a previously reserved RTP port"""
        with self.lock:
            if port in self.rtp_ports_in_use:
                self.rtp_ports_in_use.remove(port)
                # Also remove the RTCP port
                if port + 1 in self.rtp_ports_in_use:
                    self.rtp_ports_in_use.remove(port + 1)

    def _parse_sdp(self, sdp_body):
        """Parse SDP body to extract media information"""
        result = {
            'media_address': None,
            'media_port': None,
            'codecs': [],
            'attributes': {}
        }

        lines = sdp_body.strip().split('\r\n')
        current_media = None

        for line in lines:
            if line.startswith('c='):
                # Connection information: c=IN IP4 192.168.1.100
                parts = line.split(' ')
                if len(parts) >= 3:
                    result['media_address'] = parts[-1]

            elif line.startswith('m='):
                # Media description: m=audio 49170 RTP/AVP 0 8 97
                parts = line.split(' ')
                if len(parts) >= 4 and parts[0] == 'm=audio':
                    current_media = 'audio'
                    result['media_port'] = int(parts[1])
                    # Extract payload types
                    for pt in parts[3:]:
                        if pt.isdigit():
                            result['codecs'].append(int(pt))

            elif line.startswith('a=') and current_media == 'audio':
                # Attribute: a=rtpmap:97 speex/8000
                if line.startswith('a=rtpmap:'):
                    parts = line[9:].split(' ')
                    if len(parts) >= 2:
                        pt = int(parts[0])
                        codec_info = parts[1]
                        result['attributes'][f'rtpmap:{pt}'] = codec_info

        return result

    def _modify_sdp(self, sdp_body, server_ip, media_port):
        """Modify SDP to route media through the server"""
        modified_lines = []
        lines = sdp_body.strip().split('\r\n')

        for line in lines:
            if line.startswith('c='):
                # Replace connection information with server address
                modified_lines.append(f"c=IN IP4 {server_ip}")
            elif line.startswith('m=audio'):
                # Replace media port with server's allocated port
                parts = line.split(' ')
                parts[1] = str(media_port)
                modified_lines.append(' '.join(parts))
            else:
                modified_lines.append(line)

        return '\r\n'.join(modified_lines)

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def _generate_nonce(self):
        """Generate a random nonce for authentication challenges."""
        return hashlib.md5(str(random.randint(0, 100000)).encode()).hexdigest()

    def _verify_auth(self, auth_header, uri, method):
        """Verify authentication credentials."""
        if not auth_header or not auth_header.startswith("Digest "):
            return False

        # Parse digest auth parameters
        auth_parts = {}
        for part in auth_header[7:].split(','):
            key, value = part.strip().split('=', 1)
            auth_parts[key] = value.strip('"')

        if 'username' not in auth_parts or 'response' not in auth_parts or 'nonce' not in auth_parts:
            return False

        username = auth_parts['username']
        full_uri = f"{username}@sipserver"

        if full_uri not in self.credentials:
            return False

        if full_uri not in self.auth_challenges or self.auth_challenges[full_uri].nonce != auth_parts['nonce']:
            return False

        # Verify the digest response
        password_hash = self.credentials[full_uri]
        realm = self.auth_challenges[full_uri].realm

        # Calculate expected response: HA1 = MD5(username:realm:password)
        ha1 = hashlib.md5(f"{username}:{realm}:{password_hash}".encode()).hexdigest()

        # HA2 = MD5(method:uri)
        ha2 = hashlib.md5(f"{method}:sip:{uri}".encode()).hexdigest()

        # Response = MD5(HA1:nonce:HA2)
        expected_response = hashlib.md5(f"{ha1}:{auth_parts['nonce']}:{ha2}".encode()).hexdigest()

        return auth_parts['response'] == expected_response

    def _create_auth_challenge(self, uri):
        """Create a new authentication challenge for the URI."""
        nonce = self._generate_nonce()
        challenge = AuthChallenge(uri, nonce)
        self.auth_challenges[uri] = challenge
        return challenge

    def _cleanup_expired_registrations(self):
        """Remove expired registrations."""
        with self.lock:
            expired_uris = [uri for uri, endpoint in self.endpoints.items() if endpoint.is_expired()]
            for uri in expired_uris:
                logger.info(f"Removing expired registration for {uri}")
                del self.endpoints[uri]

    def _cleanup_expired_challenges(self):
        """Remove expired authentication challenges."""
        with self.lock:
            expired_uris = [uri for uri, challenge in self.auth_challenges.items() if challenge.is_expired()]
            for uri in expired_uris:
                del self.auth_challenges[uri]

    def _cleanup_ended_calls(self):
        """Clean up ended calls after a grace period"""
        with self.lock:
            current_time = time.time()
            expired_calls = []

            for call_id, call in self.calls.items():
                if call.end_time and (current_time - call.end_time) > 300:  # 5 minutes grace period
                    expired_calls.append(call_id)

                    # Clean up RTP session if exists
                    if call_id in self.rtp_sessions:
                        rtp_session = self.rtp_sessions[call_id]
                        if rtp_session.from_rtp_port:
                            self._release_rtp_port(rtp_session.from_rtp_port)
                        if rtp_session.to_rtp_port:
                            self._release_rtp_port(rtp_session.to_rtp_port)
                        del self.rtp_sessions[call_id]

            for call_id in expired_calls:
                del self.calls[call_id]
                logger.info(f"Removed expired call record for call_id {call_id}")

    def start(self):
        """Start the SIP server."""
        # Create SIP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))

        # Create RTP socket
        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp_socket.bind((self.host, 0))  # Bind to any port

        self.running = True

        logger.info(f"SIP server started on {self.host}:{self.port}")
        logger.info(f"RTP proxy started on {self.host}:{self.rtp_socket.getsockname()[1]}")

        # Start maintenance thread
        maintenance_thread = threading.Thread(target=self._maintenance_task)
        maintenance_thread.daemon = True
        maintenance_thread.start()

        # Start RTP listener thread
        rtp_thread = threading.Thread(target=self._handle_rtp)
        rtp_thread.daemon = True
        rtp_thread.start()

        # Main server loop for SIP messages
        try:
            while self.running:
                data, client_address = self.socket.recvfrom(4096)
                if data:
                    # Process the message in a separate thread
                    threading.Thread(target=self._handle_message,
                                     args=(data.decode(), client_address)).start()
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        """Stop the SIP server."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

        # Stop RTP threads
        for port, thread in self.rtp_threads.items():
            if thread.is_alive():
                # We can't directly stop threads in Python, but the socket.close() will cause the thread to exit
                pass

        if self.rtp_socket:
            self.rtp_socket.close()
            self.rtp_socket = None

        logger.info("SIP server stopped")

    def _handle_rtp(self):
        """Handle incoming RTP packets"""
        while self.running and self.rtp_socket:
            try:
                data, client_address = self.rtp_socket.recvfrom(8192)  # Larger buffer for RTP
                if data:
                    # Process RTP packet in a separate thread to avoid blocking
                    threading.Thread(target=self._process_rtp_packet,
                                     args=(data, client_address)).start()
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    logger.error(f"Error handling RTP packet: {str(e)}")

    def _process_rtp_packet(self, data, client_address):
        """Process an RTP packet and forward it to the appropriate endpoint"""
        # Try to parse as an RTP packet
        rtp_packet = RTPPacket.parse(data)
        if not rtp_packet:
            logger.warning(f"Received invalid RTP packet from {client_address}")
            return

        # Find the RTP session this packet belongs to
        client_ip, client_port = client_address
        source_session = None

        with self.lock:
            for call_id, session in self.rtp_sessions.items():
                if session.active:
                    # Check if packet is from the 'from' endpoint
                    if (session.from_endpoint.ip == client_ip and
                            (session.from_rtp_port == client_port or session.from_rtcp_port == client_port)):
                        source_session = session
                        target_ip = session.to_endpoint.ip
                        target_port = session.to_rtp_port if client_port == session.from_rtp_port else session.to_rtcp_port
                        session.packets_from_to += 1
                        session.bytes_from_to += len(data)
                        break

                    # Check if packet is from the 'to' endpoint
                    elif (session.to_endpoint.ip == client_ip and
                          (session.to_rtp_port == client_port or session.to_rtcp_port == client_port)):
                        source_session = session
                        target_ip = session.from_endpoint.ip
                        target_port = session.from_rtp_port if client_port == session.to_rtp_port else session.from_rtcp_port
                        session.packets_to_from += 1
                        session.bytes_to_from += len(data)
                        break

        if not source_session:
            logger.warning(f"Received RTP packet from unknown source: {client_address}")
            return

        # Forward the packet
        try:
            self.rtp_socket.sendto(data, (target_ip, target_port))
            logger.debug(f"Forwarded RTP packet from {client_address} to {target_ip}:{target_port}")
        except Exception as e:
            logger.error(f"Error forwarding RTP packet: {str(e)}")

    def _maintenance_task(self):
        """Periodic maintenance task to clean up expired data."""
        while self.running:
            self._cleanup_expired_registrations()
            self._cleanup_expired_challenges()
            self._cleanup_ended_calls()
            time.sleep(60)  # Run every 60 seconds

    def _handle_message(self, data, client_address):
        """Handle incoming SIP message."""
        client_ip, client_port = client_address
        logger.debug(f"Received message from {client_ip}:{client_port}")

        sip_msg = SIPMsgFactory.parse(data)
        if not sip_msg:
            logger.warning(f"Invalid SIP message from {client_ip}:{client_port}")
            return

        if isinstance(sip_msg, SIPRequest):
            self._handle_request(sip_msg, client_address)
        elif isinstance(sip_msg, SIPResponse):
            self._handle_response(sip_msg, client_address)

    def _handle_request(self, request, client_address):
        """Handle SIP request."""
        client_ip, client_port = client_address

        if request.method == SIPMethod.REGISTER.value:
            self._handle_register(request, client_address)
        elif request.method == SIPMethod.INVITE.value:
            self._handle_invite(request, client_address)
        elif request.method == SIPMethod.ACK.value:
            self._handle_ack(request, client_address)
        elif request.method == SIPMethod.BYE.value:
            self._handle_bye(request, client_address)
        else:
            # Method not supported
            response = self._create_response(
                request,
                SIPStatusCode.METHOD_NOT_ALLOWED,
                additional_headers={'Allow': 'REGISTER, INVITE, ACK, BYE'}
            )
            self._send_response(response, client_address)

    def _handle_response(self, response, client_address):
        """Handle SIP response - typically for forwarding to other endpoints."""
        call_id = response.headers.get('call-id')
        if not call_id or call_id not in self.calls:
            logger.warning(f"Received response for unknown call: {call_id}")
            return

        call = self.calls[call_id]

        # Check if this is a response to an INVITE with SDP
        if "200" in response.status_code and call_id in self.calls:
            cseq_header = response.headers.get('cseq', '')
            if 'INVITE' in cseq_header and response.body:
                # This is a 200 OK response to an INVITE with SDP
                # Extract and modify SDP for RTP proxying
                call.sdp_to = response.body
                sdp_info = self._parse_sdp(response.body)

                if sdp_info['media_port'] and sdp_info['media_address']:
                    to_endpoint = self.endpoints.get(call.to_uri)
                    from_endpoint = self.endpoints.get(call.from_uri)

                    if to_endpoint and from_endpoint and call_id in self.rtp_sessions:
                        rtp_session = self.rtp_sessions[call_id]

                        # Save callee's RTP ports
                        rtp_session.to_rtp_port = sdp_info['media_port']
                        rtp_session.to_rtcp_port = sdp_info['media_port'] + 1

                        # Modify SDP to point to our server
                        modified_sdp = self._modify_sdp(
                            response.body,
                            self.host,
                            rtp_session.from_rtp_port  # Use the port allocated for the caller
                        )
                        response.set_body(modified_sdp)

        # Forward the response to the appropriate endpoint
        target_uri = call.from_uri if response.headers.get('to') == call.to_uri else call.to_uri

        if target_uri in self.endpoints:
            target_endpoint = self.endpoints[target_uri]
            self._send_message(str(response), (target_endpoint.ip, target_endpoint.port))

    def _handle_register(self, request, client_address):
        """Handle REGISTER request."""
        client_ip, client_port = client_address
        from_uri = request.headers.get('from')

        # Check authentication if required
        if self.auth_required:
            auth_header = request.headers.get('authorization')

            # If no auth header or auth fails, send challenge
            if not auth_header or not self._verify_auth(auth_header, request.uri, "REGISTER"):
                challenge = self._create_auth_challenge(from_uri)

                # Create 401 Unauthorized response with auth challenge
                response = self._create_response(
                    request,
                    SIPStatusCode.UNAUTHORIZED,
                    additional_headers={
                        'WWW-Authenticate': f'Digest realm="{challenge.realm}", nonce="{challenge.nonce}"'
                    }
                )
                self._send_response(response, client_address)
                return

        # Process registration
        expires = int(request.headers.get('expires', 3600))

        with self.lock:
            if expires > 0:
                # Register or update registration
                if from_uri in self.endpoints:
                    self.endpoints[from_uri].update_registration(client_ip, client_port, expires)
                    logger.info(f"Updated registration for {from_uri}")
                else:
                    self.endpoints[from_uri] = SIPEndpoint(from_uri, client_ip, client_port, expires)
                    logger.info(f"New registration for {from_uri}")
            else:
                # Unregister
                if from_uri in self.endpoints:
                    del self.endpoints[from_uri]
                    logger.info(f"Unregistered {from_uri}")

        # Send 200 OK response
        response = self._create_response(
            request,
            SIPStatusCode.OK,
            additional_headers={'Expires': str(expires)}
        )
        self._send_response(response, client_address)

    def _handle_invite(self, request, client_address):
        """Handle INVITE request for call setup."""
        client_ip, client_port = client_address
        from_uri = request.headers.get('from')
        to_uri = request.headers.get('to')
        call_id = request.headers.get('call-id')

        # Check authentication if required
        if self.auth_required:
            auth_header = request.headers.get('authorization')

            # If no auth header or auth fails, send challenge
            if not auth_header or not self._verify_auth(auth_header, request.uri, "INVITE"):
                challenge = self._create_auth_challenge(from_uri)

                # Create 401 Unauthorized response with auth challenge
                response = self._create_response(
                    request,
                    SIPStatusCode.UNAUTHORIZED,
                    additional_headers={
                        'WWW-Authenticate': f'Digest realm="{challenge.realm}", nonce="{challenge.nonce}"'
                    }
                )
                self._send_response(response, client_address)
                return

        # Check if target endpoint is registered
        if to_uri not in self.endpoints:
            # Target not found
            response = self._create_response(request, SIPStatusCode.NOT_FOUND)
            self._send_response(response, client_address)
            return

        # Extract SDP information for RTP proxying
        if request.body:
            sdp_info = self._parse_sdp(request.body)
            from_rtp_