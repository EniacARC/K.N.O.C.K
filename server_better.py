import socket
import threading
import time
import hashlib
import random
import logging
from sip_msgs import SIPMsgFactory, SIPMethod, SIPStatusCode, SIPRequest, SIPResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sip_server')


class SIPEndpoint:
    def __init__(self, uri, ip, port, expires=3600):
        self.uri = uri
        self.ip = ip
        self.port = port
        self.expires = expires
        self.last_seen = time.time()
        self.calls = set()  # Store active call IDs

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

    def establish(self):
        self.established = True
        self.start_time = time.time()

    def terminate(self):
        self.established = False
        self.end_time = time.time()

    def get_duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0


class SIPServer:
    def __init__(self, host='0.0.0.0', port=5060, auth_required=True):
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

    def start(self):
        """Start the SIP server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        self.running = True

        logger.info(f"SIP server started on {self.host}:{self.port}")

        # Start maintenance thread
        maintenance_thread = threading.Thread(target=self._maintenance_task)
        maintenance_thread.daemon = True
        maintenance_thread.start()

        # Main server loop
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
        logger.info("SIP server stopped")

    def _maintenance_task(self):
        """Periodic maintenance task to clean up expired data."""
        while self.running:
            self._cleanup_expired_registrations()
            self._cleanup_expired_challenges()
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

        # Create or update call record
        with self.lock:
            if call_id not in self.calls:
                self.calls[call_id] = SIPCall(call_id, from_uri, to_uri)
                # Add call to endpoints' active calls
                if from_uri in self.endpoints:
                    self.endpoints[from_uri].calls.add(call_id)
                if to_uri in self.endpoints:
                    self.endpoints[to_uri].calls.add(call_id)

        # Send 100 Trying response
        trying_response = self._create_response(request, SIPStatusCode.TRYING)
        self._send_response(trying_response, client_address)

        # Forward INVITE to target
        target_endpoint = self.endpoints[to_uri]
        self._send_message(str(request), (target_endpoint.ip, target_endpoint.port))

    def _handle_ack(self, request, client_address):
        """Handle ACK request for call establishment."""
        call_id = request.headers.get('call-id')

        if call_id in self.calls:
            # Mark call as established
            with self.lock:
                self.calls[call_id].establish()

            # Forward ACK to target
            to_uri = request.headers.get('to')
            if to_uri in self.endpoints:
                target_endpoint = self.endpoints[to_uri]
                self._send_message(str(request), (target_endpoint.ip, target_endpoint.port))
        else:
            logger.warning(f"Received ACK for unknown call: {call_id}")

    def _handle_bye(self, request, client_address):
        """Handle BYE request for call termination."""
        call_id = request.headers.get('call-id')
        from_uri = request.headers.get('from')
        to_uri = request.headers.get('to')

        # Check if call exists
        if call_id not in self.calls:
            # Call not found
            response = self._create_response(request, SIPStatusCode.CALL_DOES_NOT_EXIST)
            self._send_response(response, client_address)
            return

        # Terminate the call
        with self.lock:
            self.calls[call_id].terminate()
            # Remove call from endpoints' active calls
            if from_uri in self.endpoints:
                self.endpoints[from_uri].calls.discard(call_id)
            if to_uri in self.endpoints:
                self.endpoints[to_uri].calls.discard(call_id)

            # Log call duration
            logger.info(f"Call {call_id} terminated, duration: {self.calls[call_id].get_duration():.2f}s")

            # Keep call record for a while (could be moved to a separate cleanup task)
            # del self.calls[call_id]

        # Send 200 OK response
        response = self._create_response(request, SIPStatusCode.OK)
        self._send_response(response, client_address)

        # Forward BYE to target
        target_uri = to_uri if from_uri == request.headers.get('from') else from_uri
        if target_uri in self.endpoints:
            target_endpoint = self.endpoints[target_uri]
            self._send_message(str(request), (target_endpoint.ip, target_endpoint.port))

    def _create_response(self, request, status_code, additional_headers=None):
        """Create a SIP response based on the request."""
        # Fix the SIPMsgFactory.create_response method from the original framework
        response = SIPResponse()
        response.status_code = status_code.value  # Use the tuple from enum
        response.version = request.version

        # Copy required headers
        response.headers = {
            'to': request.headers.get('to'),
            'from': request.headers.get('from'),
            'call-id': request.headers.get('call-id'),
            'cseq': request.headers.get('cseq'),
            'content-length': '0'
        }

        # Add additional headers
        if additional_headers:
            for key, value in additional_headers.items():
                response.set_header(key, value)

        # Set body if needed
        if request.body and status_code == SIPStatusCode.OK:
            response.set_body(request.body)

        return response

    def _send_response(self, response, address):
        """Send SIP response to the client."""
        self._send_message(str(response), address)

    def _send_message(self, message, address):
        """Send SIP message to the given address."""
        if not self.socket or not self.running:
            logger.warning("Cannot send message: server not running")
            return

        try:
            self.socket.sendto(message.encode(), address)
            logger.debug(f"Sent message to {address[0]}:{address[1]}")
        except Exception as e:
            logger.error(f"Error sending message to {address[0]}:{address[1]}: {str(e)}")

    def get_registered_endpoints(self):
        """Get a list of registered endpoints for monitoring."""
        with self.lock:
            return [str(endpoint) for endpoint in self.endpoints.values()]

    def get_active_calls(self):
        """Get a list of active calls for monitoring."""
        with self.lock:
            return [
                f"Call: {call_id} - From: {call.from_uri} To: {call.to_uri} - " +
                f"Status: {'Active' if call.established else 'Setting up'} - " +
                f"Duration: {call.get_duration():.2f}s"
                for call_id, call in self.calls.items() if call.established or not call.end_time
            ]


if __name__ == "__main__":
    server = SIPServer(host='0.0.0.0', port=5060, auth_required=True)

    try:
        # Start server in a separate thread
        server_thread = threading.Thread(target=server.start)
        server_thread.daemon = True
        server_thread.start()

        # Main loop for monitoring
        print("SIP Server running. Press Ctrl+C to exit.")
        while True:
            print("\n==== Server Status ====")
            print("Registered Endpoints:")
            for endpoint in server.get_registered_endpoints():
                print(f"  - {endpoint}")

            print("\nActive Calls:")
            for call in server.get_active_calls():
                print(f"  - {call}")

            time.sleep(10)

    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()
        print("Server stopped.")