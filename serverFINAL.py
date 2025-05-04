import concurrent.futures
from sip_msgs import *
from authentication import *
import socket
import datetime
import threading
import time
from dataclasses import dataclass
from enum import Enum
from comms import *
import select
# from sdp_class import *
from typing import Optional
from collections import Counter

# Constants
DEFAULT_SERVER_PORT = 5040
MAX_WORKERS = 10
SIP_VERSION = "SIP/2.0"
SERVER_URI = "myserver"
SERVER_IP = '127.0.0.1'  # need to find out using sbc
CALL_IDLE_LIMIT = 15
REGISTER_LIMIT = 60
REQUIRED_HEADERS = {'to', 'from', 'call-id', 'cseq', 'content-length'}
KEEP_ALIVE_MSG = SIPMsgFactory.create_request(SIPMethod.OPTIONS, SIP_VERSION, "keep-alive", "keep-alive",
                                              "", "1")
MAX_PASSES_META = 8000  # 8 kb
MAX_PASSES_BODY = 100



@dataclass
class RegisteredUser:
    """ Struct for registered user """
    uri: str
    address: (str, int)
    socket: socket.socket
    registration_time: datetime.datetime
    expires: int  # amount of seconds


# @dataclass
# class SDPProxyInfo:
#     sdp_msg: SDP
#     swap_ip: str
#     swap_audio_port = Optional[int]
#     swap_video_port = Optional[int]


# Dataclasses for storing session info for each message type
@dataclass
class Call:  # For both invite and register
    call_type: SIPCallType
    call_id: str
    uri: str  # Either caller or callee depending on call type
    call_state: SIPCallState
    last_used_cseq_num: int
    last_active: datetime.datetime
    callee_socket: socket.socket = None
    caller_socket: Optional[socket.socket] = None
    uri_other: Optional[str] = None


@dataclass
class KeepAlive:
    # Keep alive is for connection - not for registered uacs, so it's socket context
    call_id: str
    last_used_cseq_num: int
    client_socket: socket.socket


@dataclass
class AuthChallenge:
    # this is for remembering auth data sent to the client
    answer: str
    created_time: datetime.datetime


class BiMap:
    def __init__(self, key_attr: str, value_attr: str):
        """
        Initialize a bidirectional map using attributes from stored objects.

        :param key_attr: Attribute name to use as key in the first map (e.g., 'socket')
        :param value_attr: Attribute name to use as key in the second map (e.g., 'uri')
        """
        self.key_to_val = {}  # e.g., socket -> uri
        self.val_to_obj = {}  # e.g., uri -> full object
        self.key_attr = key_attr
        self.value_attr = value_attr

    def add(self, obj):
        key = getattr(obj, self.key_attr)
        val = getattr(obj, self.value_attr)
        self.key_to_val[key] = val
        self.val_to_obj[val] = obj

    def remove_by_key(self, key):
        if key in self.key_to_val:
            val = self.key_to_val.pop(key)
            self.val_to_obj.pop(val, None)
            return True
        return False

    def remove_by_val(self, val):
        if val in self.val_to_obj:
            obj = self.val_to_obj.pop(val)
            key = getattr(obj, self.key_attr)
            self.key_to_val.pop(key, None)
            return True
        return False

    def get_by_val(self, val):
        return self.val_to_obj.get(val)

    def get_by_key(self, key):
        val = self.key_to_val.get(key)
        return self.val_to_obj.get(val) if val else None


class SIPServer:
    def __init__(self, port=DEFAULT_SERVER_PORT):
        # Socket properties
        self.host = '0.0.0.0'
        self.port = port
        self.server_socket = None
        self.running = False
        self.queue_len = 5
        # for the future dos blocker
        # self.connection_counts = Counter()  # For IP rate limiting - ip -> int
        # self.max_connections_per_ip = 100

        # Thread pool properties
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="sip_worker"
        )

        # Locks - RLock for multiple acquisitions in the same thread
        self.reg_lock = threading.RLock()  # Lock for adding users to the registered_users dict
        self.call_lock = threading.RLock()  # Lock for adding users to the active_calls dict
        self.conn_lock = threading.RLock()

        # User management properties
        self.registered_user = BiMap(key_attr="socket", value_attr="uri")

        # call lock
        self.active_calls = {}  # call lock. call-id -> Call
        # no use for bi map here. there can be a socket in multiple calls still O(n)
        self.pending_auth = {}  # uri -> AuthChallenge
        self.authority = AuthService(SERVER_URI)

        # Connection management - con lock
        self.connected_users = []  # sockets
        self.pending_keep_alive = {}  # call-id -> KeepAlive

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.running = True
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.queue_len)

            # Clean any expired registrations or inactive users
            cleanup_thread = threading.Thread(target=self._cleanup_expired_reg, daemon=True)
            keepalive_thread = threading.Thread(target=self._keep_alive, daemon=True)
            cleanup_thread.start()
            keepalive_thread.start()

            # Start server loop
            while self.running:
                with self.conn_lock:
                    readable, _, _ = select.select(self.connected_users + [self.server_socket], [], [], 0.5)
                for sock in readable:
                    if sock is self.server_socket:
                        # Incoming connection
                        client_sock, addr = self.server_socket.accept()
                        # Check if IP blacklisted
                        # Add addr to table. If too many entries in a short amount of time then DOS block IP.
                        with self.conn_lock:
                            self.connected_users.append(client_sock)
                    else:
                        # returns sip msg object and checks is in format and in valid bounds
                        msg = receive_tcp_sip(sock, MAX_PASSES_META, MAX_PASSES_BODY)
                        if msg:
                            self.thread_pool.submit(self._worker_process_msg, sock, msg)
                        else:
                            self._close_connection(sock)
        except socket.error as err:
            print(err + "something went wrong!")
        finally:
            self.running = False
            with self.conn_lock:
                while self.connected_users:
                    self.connected_users.pop().close()
            self.server_socket.close()

    def _worker_process_msg(self, sock, msg):
        # sip_msg = SIPMsgFactory.parse(msg.decode())
        # if not sip_msg:
        #     print("error! invalid sip msg - cannot respond")
        #     return
        if isinstance(msg, SIPRequest):
            self.process_request(sock, msg)
        else:
            self.process_request(sock, msg)

    def process_request(self, sock, req):
        not_valid = self._check_request_validly(req)
        if not_valid:
            self._send_to_client(sock, str(not_valid).encode())
            if not_valid.get_header('call-id'):
                with self.call_lock:
                    call_obj = self.active_calls[req.get_header('call-id')]
                    if call_obj:
                        call_obj.last_used_cseq_num += 1  # Next request expects the next cseq number
        else:
            method = req.method
            if method == SIPMethod.REGISTER:
                pass  # Handle register
            elif method == SIPMethod.INVITE:
                pass  # Handle invite
            elif method == SIPMethod.ACK:
                pass  # Handle ACK end of invite - start RTP
            elif method == SIPMethod.BYE:
                pass  # Handle BYE

    def _check_request_validly(self, msg):
        error_msg = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, SERVER_URI)
        if msg.version != SIP_VERSION:
            error_msg.status_code = SIPStatusCode.VERSION_NOT_SUPPORTED
            error_msg.version = SIP_VERSION
        elif REQUIRED_HEADERS.issubset(msg.headers):
            error_msg.status_code = SIPStatusCode.BAD_REQUEST
            missing = REQUIRED_HEADERS - msg.headers.keys()
            for header in missing:
                error_msg.set_header(header, "missing")
        elif msg.get_header['cseq'][1] != msg.method.lower():
            error_msg.status_code = SIPStatusCode.BAD_REQUEST
            error_msg.set_header('cseq', [msg.get_header['cseq'][0], msg.method.lower()])
        # elif len(msg.body) != msg.get_header('content-length'):
        #     error_msg.status_code = SIPStatusCode.BAD_REQUEST

        if error_msg.status_code == SIPStatusCode.OK:
            return None
        return error_msg

    def ack_request(self, sock, req):
        # pass ack to the other side start rtp
        pass

    def bye_request(self, sock, req):
        # close the call
        # close rtp call send bye to other side terminate call
        pass

    def cancel_request(self, sock, req):
        # in register uri the uri you are trying to register
        uri_sender = req.get_header('from')
        uri_recv = req.get_header('to')
        call_id = req.get_header("call-id")
        cseq = req.get_header('cseq')[0]
        with self.call_lock:  # it's better to get the lock for the whole func instead of acquiring multiple times
            # verify call details are the ok
            call = None
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                if cseq != call.cseq + 1 or call.uri != uri_recv or call.method != req.method or call.method != SIPMethod.INVITE or sock is not call.callee_socket or call.call_state != SIPCallState.RINGING:
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
                    # the call is in the correct state and can be canceled

            # send ok response so the client knows I received. the canceling side must be the callee
            res_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.OK, SERVER_URI)
            self._send_to_client(sock, str(res_msg).encode())

            # send cancel to the other side
            req.set_header('cseq', cseq + 1, req.get_header('cseq')[1])
            req.set_header('from', SERVER_URI)
            if call.uri_other is not None:
                # other uri in invite is always the
                req.set_header('to', call.uri_other)
            else:
                req.set_header('to', 'cancel')

            self._send_to_client(call.caller_socket, str(req).encode())

    def invite_request(self, sock, req):
        # in register uri the uri you are trying to register
        uri_sender = req.get_header('from')
        uri_recv = req.get_header('to')
        call_id = req.get_header("call-id")
        cseq = req.get_header('cseq')[0]
        with self.call_lock:  # it's better to get the lock for the whole func instead of acquiring multiple times
            # verify call details are the ok
            call = None
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                if cseq != call.cseq + 1 or call.uri != uri_recv or call.method != req.method or call.method != SIPMethod.INVITE or sock is not call.caller_socket:
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
            else:
                call = Call(
                    call_type=SIPCallType.INVITE,
                    call_id=call_id,
                    uri=uri_recv,
                    caller_socket=sock,
                    call_state=SIPCallState.WAITING_AUTH,
                    last_used_cseq_num=cseq,
                    last_active=datetime.datetime.now()
                )
                self.active_calls[call_id] = call
            call.last_used_cseq_num += 1
            call.last_active = datetime.datetime.now()

            # made sure the user is auth
            # make sure we can call the callee
            is_auth = False
            auth_header = req.get_header('WWW-Authenticate')
            user_recv = None
            with self.reg_lock:
                user_recv = self.registered_user.get_by_val(uri_recv)
                if not user_recv:
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.NOT_FOUND, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
                if self.registered_user.get_by_val(uri_sender) and self.registered_user.get_by_key(sock):
                    is_auth = True
                    call.uri_other = self.registered_user.get_by_key(sock).uri  # set the other uri in the call

            # now we know who are we trying to call
            call.callee_socket = user_recv.socket

            if auth_header:
                if not is_auth:
                    if call_id not in self.pending_auth:
                        # auth request was either timed out or never sent
                        self._create_auth_challenge(sock, req)
                        return
                    # verify auth response
                    auth_header_parsed = self._parse_auth_header(auth_header)
                    if not auth_header_parsed:
                        error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST,
                                                                               SERVER_URI)
                        self._send_to_client(sock, str(error_msg).encode())
                        return
            else:
                if call.call_state == SIPCallState.WAITING_AUTH:
                    self._create_auth_challenge(sock, req)
                    return
                # the call in this connection was authenticated no need to authenticate again

            # now we know the user is authenticated we can proceed to send the invite

            if call_id in self.pending_auth:
                del self.pending_auth

            call.call_state = SIPCallState.TRYING
            if not req.body:
                error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                self._send_to_client(sock, str(error_msg).encode())
                return
            self._send_to_client(user_recv.socket, str(req).encode())
            self._send_to_client(sock,
                                 SIPMsgFactory.create_response_from_request(req, SIPStatusCode.TRYING, SERVER_URI))

    def register_request(self, sock, req):

        # in register uri the uri you are trying to register
        uri = req.get_header('from')
        to_uri = req.get_header('to')
        call_id = req.get_header("call-id")
        cseq = req.get_header('cseq')[0]
        expires = REGISTER_LIMIT
        if req.get_header('expires'):
            expires = int(req.get_header('expires'))

        if to_uri != SERVER_URI:
            # register is to the server only
            error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_GATEWAY, SERVER_URI)
            self._send_to_client(sock, str(error_msg).encode())
            return

        with self.call_lock:
            # verify call details are the ok
            call = None
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                if cseq != call.cseq + 1 or call.uri != uri or call.method != req.method or call.method != SIPMethod.REGISTER or sock is not call.caller_socket:
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
            else:
                call = Call(
                    call_type=SIPCallType.REGISTER,
                    call_id=call_id,
                    uri=uri,
                    uri_other=SERVER_URI,
                    callee_socket=self.server_socket,
                    caller_socket=sock,
                    call_state=SIPCallState.WAITING_AUTH,
                    last_used_cseq_num=cseq,
                    last_active=datetime.datetime.now(),
                )
                self.active_calls[call_id] = call
            call.last_used_cseq_num += 1
            call.last_active = datetime.datetime.now()

        with self.reg_lock:
            if self.registered_user.get_by_key(sock):
                if self.registered_user.get_by_val(call_id).socket == sock:
                    # this is the same user in the same connection that was already authenticated
                    with self.reg_lock:
                        user = RegisteredUser(
                            uri=uri,
                            address=sock.getpeername(),
                            socket=sock,
                            registration_time=datetime.datetime.now(),
                            expires=expires,
                        )
                        self.registered_user.add(user)  # overrides previous register if exists
                        self._send_to_client(sock, SIPMsgFactory.create_response_from_request(req, SIPStatusCode.OK,
                                                                                              SERVER_URI))
                    del self.active_calls[call_id]  # remove call
        auth_header = req.get_header('WWW-Authenticate')
        if auth_header:
            with self.call_lock:
                if call_id not in self.pending_auth:
                    # auth request was either timed out or never sent
                    self._create_auth_challenge(sock, req)
                    return
                # verify auth response
                auth_header_parsed = self._parse_auth_header(auth_header)
                if not auth_header_parsed:
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                else:
                    answer_now = str(
                        self.authority.calculate_hash_auth(auth_header_parsed['username'], SIPMethod.REGISTER,
                                                           auth_header_parsed['nonce'],
                                                           auth_header_parsed['realm']))

                    if answer_now != auth_header_parsed['response'] or answer_now != self.pending_auth[call_id].answer:
                        error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.FORBIDDEN, SERVER_URI)
                        self._send_to_client(sock, str(error_msg).encode())
                    else:
                        # user authenticated
                        del self.pending_auth[call_id]
                        del self.active_calls[call_id]
                        print("user authenticated")
                        with self.reg_lock:
                            user = RegisteredUser(
                                uri=uri,
                                address=sock.getpeername(),
                                socket=sock,
                                registration_time=datetime.datetime.now(),
                                expires=expires,
                            )
                            self.registered_user.add(user)  # overrides previous register if exists
                            self._send_to_client(sock,
                                                 SIPMsgFactory.create_response_from_request(req, SIPStatusCode.OK,
                                                                                            SERVER_URI))

        else:
            self._create_auth_challenge(sock, req)

    def _parse_auth_header(self, header) -> dict | None:
        """
        Parses a Digest Authorization header into a dictionary.
        Returns None if the format is invalid or required fields are missing.
        """
        if not header or not header.lower().startswith("digest "):
            return None

        header = header[7:].strip()

        # Regex for key="value" or key=value (handles both quoted/unquoted)
        pattern = re.compile(r'(\w+)=("([^"\\]*(\\.[^"\\]*)*)"|[^,]+)')
        parsed = {}

        for match in pattern.finditer(header):
            key = match.group(1)
            raw_value = match.group(3) if match.group(3) is not None else match.group(2)
            parsed[key] = raw_value.strip().strip('"')

        # Validate required fields for Digest auth (can be expanded if needed)
        required_fields = ['username', 'realm', 'nonce', 'response']
        if not all(field in parsed for field in required_fields):
            return None

        return parsed

    def _create_auth_challenge(self, sock, request):
        """Send authentication challenge for REGISTER request"""
        method = request.method
        call_id = request.get_header('call-id')
        uri = request.get_header('from')

        # Store challenge
        with self.call_lock:
            # Generate nonce
            nonce = AuthService.generate_nonce()
            # Create challenge
            challenge = AuthChallenge(
                answer=str(self.authority.calculate_hash_auth(uri, method, nonce)),
                created_time=datetime.datetime.now()
            )
            self.pending_auth[call_id] = challenge

        auth_header = f'Digest realm="{SERVER_URI}", nonce="{nonce}, algorithm=MD5'
        # Create challenge response
        response = SIPMsgFactory.create_response_from_request(request, SIPStatusCode.UNAUTHORIZED,
                                                              SERVER_URI, [("www-authenticate", auth_header)])
        response.set_header('from', SERVER_URI)
        self._send_to_client(sock, str(response).encode())

    def process_response(self, sock, res):
        not_valid = self._check_response_valid(res)
        if not_valid:
            self._send_to_client(sock, str(not_valid).encode())

        uri = res.get_header('from')
        to_uri = res.get_header('to')
        call_id = res.get_header("call-id")
        cseq = res.get_header('cseq')[0]
        call_id = res.get_header('call-id')
        with self.call_lock:
            if call_id not in self.active_calls and call_id not in self.pending_keep_alive:
                # the call doesn't exist
                not_valid.status_code = SIPStatusCode.NOT_FOUND
                self._send_to_client(sock, str(not_valid).encode())
                return
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                if not cseq != call.last_used_cseq_num:
                    not_valid.status_code = SIPStatusCode.BAD_REQUEST
                    self._send_to_client(sock, str(not_valid).encode())
                    return
                call.last_active = datetime.datetime.now()

        if call_id in self.pending_keep_alive:
            with self.conn_lock:
                # The response is to a keep alive
                if res.status_code is SIPStatusCode.OK and res.get_header('cseq') == str(
                        self.pending_keep_alive[call_id].last_used_cseq_num):
                    del self.pending_keep_alive[call_id]  # The response was valid so the connection is kept alive
                # Else response is invalid, and we drop them at the next keep_alive check
        else:
            # If not keep alive then it's for an invite call
            with self.call_lock:
                call = self.active_calls[call_id]
                if call.call_type == SIPCallType.INVITE:
                    # now we check if we can advance state. if we cannot then we send and error response

                    # this is if the call goes accordingly
                    if call.call_state == SIPCallState.TRYING and res.status_code == SIPStatusCode.RINGING:
                        call.call_state = SIPCallState.RINGING
                    elif call.call_state == SIPCallState.RINGING and res.status_code == SIPStatusCode.OK:
                        call.call_state = SIPCallState.WAITING_ACK
                        # proccess sdp for the other side
                        if not res.body:
                            not_valid.status_code = SIPStatusCode.BAD_REQUEST
                            self._send_to_client(sock, str(not_valid).encode())
                            return
                    elif call.call_state == SIPCallState.INIT_CANCEL and res.status_code == SIPStatusCode.OK:
                        call.call_state = SIPCallState.TRYING_CANCEL
                        return  # no need to forward status code
                    elif call.call_state == SIPCallState.TRYING_CANCEL and res.status_code == SIPStatusCode.REQUEST_TERMINATED:
                        ack_req = SIPMsgFactory.create_request(SIPMethod.ACK, SIP_VERSION, uri, SERVER_URI, call_id,
                                                               cseq + 1)
                        self._send_to_client(sock, str(ack_req).encode())
                        del self.active_calls[call_id]

                    else:
                        not_valid.status_code = SIPStatusCode.NOT_ACCEPTABLE
                        self._send_to_client(sock, str(not_valid).encode())
                        return  # we do not want to foward thhe invalid msg

                    send_sock = call.caller_socket if sock != call.caller_socket else call.callee_socket
                    self._send_to_client(send_sock, str(res).encode())
                else:
                    # if the call was not an invite then it is not possible to send response
                    error_msg = SIPMsgFactory.create_response_from_request(res, SIPStatusCode.NOT_ACCEPTABLE_ANYWHERE,
                                                                           SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())

    def _check_response_valid(self, msg):
        error_msg = SIPMsgFactory.create_response(SIPStatusCode.OK, SIP_VERSION,
                                                  msg.get_header('cseq'), msg.get_header('to'),
                                                  msg.get_header('from'), msg.get_header('call-id'))
        if msg.version != SIP_VERSION:
            error_msg.status_code = SIPStatusCode.VERSION_NOT_SUPPORTED
            error_msg.version = SIP_VERSION
        elif REQUIRED_HEADERS.issubset(msg.headers):
            error_msg.status_code = SIPStatusCode.BAD_REQUEST
            missing = REQUIRED_HEADERS - msg.headers.keys()
            for header in missing:
                error_msg.set_header(header, "missing")
        elif msg.status_code not in SIPStatusCode:
            error_msg.status_code = SIPStatusCode.BAD_REQUEST

        # elif len(msg.body) != msg.get_header('content-length'):
        #     error_msg.status_code = SIPStatusCode.BAD_REQUEST

        if error_msg.status_code == SIPStatusCode.OK:
            return None
        return error_msg

    def _cleanup_expired_reg(self):
        """Removes registrations that are past expiration"""
        with self.reg_lock:
            for uri, user in self.registered_user.val_to_obj:
                if (datetime.datetime.now() - user.registration_time) >= user.expires:
                    self.registered_user.remove_by_val(uri)
        time.sleep(30)

    def _cleanup_inactive_calls(self):
        """Removes calls with sockets that are inactive"""
        with self.call_lock:
            for call_id, call in self.active_calls:
                if (
                        datetime.datetime.now() - call.last_active) >= CALL_IDLE_LIMIT and call.call_type != SIPCallState.IN_CALL:
                    del self.active_calls[call_id]

                    # if the call was register then we need to remove the invalid auth challenge
                    if call.uri in self.pending_auth:
                        del self.pending_auth[call.uri]
        time.sleep(30)

    def _keep_alive(self):
        while self.running:
            """Send heartbeats. If socket didn't respond to the last heartbeat then it is inactive"""
            with self.conn_lock:
                for call_id, keep_alive in self.pending_keep_alive.items():
                    # Socket should be in connected users. Check for safety
                    if keep_alive.client_socket in self.connected_users:
                        del self.pending_keep_alive[call_id]
                        self._close_connection(keep_alive.client_socket)
                # Everyone that remained has answered the keep alive
                for sock in self.connected_users:
                    msg = KEEP_ALIVE_MSG
                    call_id = generate_random_call_id()
                    msg.set_header('call-id', call_id)

                    self._send_to_client(sock, str(msg).encode())
                    keep_alive_obj = KeepAlive(call_id, 1, sock)
                    self.pending_keep_alive[call_id] = keep_alive_obj
            time.sleep(30)

    def _close_connection(self, sock):
        """Remove user from both active_users and registered_users when applicable"""
        with self.conn_lock:
            if sock in self.connected_users:
                self.connected_users.remove(sock)
                # pending_keep_alive entry would be removed by the _keep_alive func
        with self.reg_lock:
            self.registered_user.remove_by_key(sock)
        with self.call_lock:
            # Remove a call that the sock is in. If there is another UAC send them an error msg
            for call_id, call in self.active_calls:
                if call.caller_socket is sock or call.callee_socket is sock:
                    if call.call_obj.call_type == SIPCallType.INVITE:
                        send_sock = call.caller_socket if call.callee_socket == sock else call.callee_socket
                        with self.reg_lock:
                            if self.registered_user.get_by_key(send_sock):
                                to_uri = self.registered_user.get_by_key(send_sock)
                                end_msg = SIPMsgFactory.create_response(SIPStatusCode.NOT_FOUND, SIP_VERSION,
                                                                        SIPMethod.INVITE, to_uri, SERVER_URI, call)
                                self._send_to_client(sock, str(end_msg).encode())

                    if call.uri in self.pending_auth:
                        del self.pending_auth[call.uri]
                    del self.active_calls[call_id]

        sock.close()

    def _send_to_client(self, sock, data):
        if not send_tcp(sock, data):
            self._close_connection(sock)


"""
for each call have a state so you know if the msgs send are valid for the state. 
have diuffernt thred for srt. send commands through queue.
"""
