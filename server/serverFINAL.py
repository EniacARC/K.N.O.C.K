import concurrent.futures
from collections import defaultdict

from utils.authentication import *
from utils.user_database import UserDatabase
import datetime
import threading
import time
from dataclasses import dataclass
from utils.comms import *
import select
from typing import Optional

# Constants
DEFAULT_SERVER_PORT = 4552
MAX_WORKERS = 10
SIP_VERSION = "SIP/2.0"
SERVER_URI = "myserver"
SERVER_IP = '127.0.0.1'  # need to find out using sbc
CALL_IDLE_LIMIT = 15
REGISTER_LIMIT = 60
REQUIRED_HEADERS = {'to', 'from', 'call-id', 'cseq'}  #'content-length'
KEEP_ALIVE_MSG = SIPMsgFactory.create_request(SIPMethod.OPTIONS, SIP_VERSION, "keep-alive", "keep-alive",
                                              "", "1")
MAX_PASSES_META = 8000  # 8 kb
MAX_PASSES_BODY = 1000

BANNED_IPS_FILE = "banned_ips.txt"


@dataclass
class RegisteredUser:
    """ Struct for registered user """
    uri: str
    address: (str, int)
    socket: socket.socket
    registration_time: datetime.datetime
    expires: int  # amount of seconds


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
    def __init__(self, key_attr, value_attr):
        """
                Initialize a bidirectional mapping based on specified object attributes.

                :param key_attr: Attribute name used as key in the key-to-value map
                :type key_attr: str
                :param value_attr: Attribute name used as key in the value-to-object map
                :type value_attr: str
        """
        self.key_to_val = {}  # e.g., socket -> uri
        self.val_to_obj = {}  # e.g., uri -> full object
        self.key_attr = key_attr
        self.value_attr = value_attr

    def add(self, obj):
        """
        Add an object to the bidirectional map.

        :param obj: Object to be added
        :type obj: object
        """
        key = getattr(obj, self.key_attr)
        val = getattr(obj, self.value_attr)
        self.key_to_val[key] = val
        self.val_to_obj[val] = obj

    def remove_by_key(self, key):
        """
        Remove an object from the map using the key attribute.

        :param key: Key to remove the object by
        :type key: Any

        :return: True if the object was removed, False otherwise
        :rtype: bool
        """
        if key in self.key_to_val:
            val = self.key_to_val.pop(key)
            self.val_to_obj.pop(val, None)
            return True
        return False

    def remove_by_val(self, val):
        """
        Remove an object from the map using the value attribute.

        :param val: Value to remove the object by
        :type val: Any

        :return: True if the object was removed, False otherwise
        :rtype: bool
        """
        if val in self.val_to_obj:
            obj = self.val_to_obj.pop(val)
            key = getattr(obj, self.key_attr)
            self.key_to_val.pop(key, None)
            return True
        return False

    def get_by_val(self, val):
        """
        Retrieve an object by its value attribute.

        :param val: Value key to look up the object
        :type val: Any

        :return: The corresponding object if found
        :rtype: object or None
        """
        return self.val_to_obj.get(val)

    def get_by_key(self, key):
        """
        Retrieve an object by its key attribute.

        :param key: Key to look up the object
        :type key: Any

        :return: The corresponding object if found
        :rtype: object or None
        """
        val = self.key_to_val.get(key)
        return self.val_to_obj.get(val) if val else None


class SIPServer:
    def __init__(self, port=DEFAULT_SERVER_PORT):
        """
        Initialize the SIP server with default settings, including networking, thread pool, locks,
        user registration, call management, and connection tracking.

        :param port: Port on which the server will listen for incoming connections
        :type port: int
        """
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

        self.user_db = UserDatabase()
        self.authority = AuthService(SERVER_URI)

        # Locks - RLock for multiple acquisitions in the same thread
        self.reg_lock = threading.RLock()  # Lock for adding users to the registered_users dict
        self.call_lock = threading.RLock()  # Lock for adding users to the active_calls dict
        self.conn_lock = threading.RLock()
        self.ip_lock = threading.RLock()

        # User management properties
        self.registered_user = BiMap(key_attr="socket", value_attr="uri")

        # call lock
        self.active_calls = {}  # call lock. call-id -> Call
        # no use for bi map here. there can be a socket in multiple calls still O(n)
        self.pending_auth = {}  # uri -> AuthChallenge

        # Connection management - con lock
        self.connected_users = []  # sockets
        self.pending_keep_alive = {}  # call-id -> KeepAlive

        # ip lock
        self.ip_connection_counts = defaultdict(list)  # IP -> [timestamps]
        self.ip_message_counts = defaultdict(list)  # sock -> [timestamps]

        # for ip block (dos stop)
        self.blacklist_ips = set()
        self.connection_threshold = 50  # max attempts
        self.time_window = 60  # seconds
        self.max_connected = 1000

        # msg rate limiter for ddos
        self.msg_rate_limit = 100  # max allowed messages
        self.msg_time_window = 60  # seconds

    def start(self):
        """
        Start the SIP server, bind the socket, listen for connections,
        and handle SIP message reception and dispatch.
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.running = True
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.queue_len)
            print(f"listening on {self.host}:{self.port}")

            # Clean any expired registrations or inactive users
            cleanup_thread = threading.Thread(target=self._cleanup_expired_reg, daemon=True)
            keepalive_thread = threading.Thread(target=self._keep_alive, daemon=True)
            inactive_call_clean_thread = threading.Thread(target=self._cleanup_inactive_calls, daemon=True)
            ip_cleanup_thread = threading.Thread(target=self._cleanup_ip_counters, daemon=True)
            cleanup_thread.start()
            keepalive_thread.start()
            inactive_call_clean_thread.start()
            ip_cleanup_thread.start()

            self._load_banned_ips()

            # Start server loop
            while self.running:
                with self.conn_lock:
                    readable, _, _ = select.select(self.connected_users + [self.server_socket], [], [], 0.5)
                for sock in readable:
                    if sock is self.server_socket:
                        # Incoming connection
                        client_sock, addr = self.server_socket.accept()
                        client_ip = addr[0]
                        if client_ip in self.blacklist_ips or len(self.connected_users) >= self.max_connected:
                            client_sock.close()
                            continue
                        # sliding window
                        with self.ip_lock:
                            now = time.time()
                            self.ip_connection_counts[client_ip] = [
                                t for t in self.ip_connection_counts[client_ip] if now - t < self.time_window
                            ]
                            self.ip_connection_counts[client_ip].append(now)

                            if len(self.ip_connection_counts[client_ip]) > self.connection_threshold:
                                print(f"Blacklisting IP {client_ip} for excessive connections.")
                                self.blacklist_ips.add(client_ip)
                                del self.ip_connection_counts[client_ip]
                                client_sock.close()
                                continue

                        with self.conn_lock:
                            # add encryption
                            self.connected_users.append(client_sock)
                        print(f"added client at {addr}")
                    else:
                        # Rate-limit messages per connection
                        with self.ip_lock:
                            now = time.time()
                            self.ip_message_counts[sock] = [
                                t for t in self.ip_message_counts[sock] if now - t < self.msg_time_window
                            ]
                            self.ip_message_counts[sock].append(now)

                            # if too many msgs close connection
                            if len(self.ip_message_counts[sock]) > self.msg_rate_limit:
                                print(f"Too many messages from {sock}, closing connection.")
                                del self.ip_message_counts[sock]
                                self._close_connection(sock)
                                continue

                        # returns sip msg object and checks is in format and in valid bounds
                        msg = receive_tcp_sip(sock, MAX_PASSES_META, MAX_PASSES_BODY)
                        print(f" got msg: {msg}")
                        if msg:
                            self.thread_pool.submit(self._worker_process_msg, sock, msg)
                        else:
                            self._close_connection(sock)
        except Exception as err:
            print(str(err) + "something went wrong!")
        finally:
            self.thread_pool.shutdown(wait=True)
            self.running = False
            with self.conn_lock:
                while self.connected_users:
                    self.connected_users.pop().close()
            self.server_socket.close()

    def _load_banned_ips(self):
        """
        Load previously banned IP addresses from the banned IPs file.

        This method reads each line from the BANNED_IPS_FILE and adds valid IP
        addresses to the self.blacklist_ips set. If the file does not exist,
        it starts with an empty blacklist and logs that information.
        """
        try:
            with open(BANNED_IPS_FILE, "r") as f:
                for line in f:
                    ip = line.strip()
                    if ip:
                        self.blacklist_ips.add(ip)
            print(f"Loaded {len(self.blacklist_ips)} banned IPs.")
        except FileNotFoundError:
            print("No banned IP file found. Starting fresh.")

    def _save_banned_ip(self):
        """
        Save the current set of blacklisted IP addresses to the banned IPs file.

        This method writes all IP addresses in the self.blacklist_ips set to
        the BANNED_IPS_FILE, one per line. It overwrites any existing entries
        with the current set of known banned IPs.
        """
        with open(BANNED_IPS_FILE, "a") as f:
            for ip in self.blacklist_ips:
                f.write(ip + "\n")

    def _worker_process_msg(self, sock, msg):
        """
        Route SIP messages to appropriate processing methods based on message type.

        :param sock: Client socket from which the message was received
        :type sock: socket.socket
        :param msg: SIP message object (request or response)
        :type msg: SIPRequest or SIPResponse
        """
        if isinstance(msg, SIPRequest):
            self.process_request(sock, msg)
        else:
            self.process_response(sock, msg)

    def process_request(self, sock, req):
        """
        Process a SIP request, including REGISTER, INVITE, ACK, and BYE methods.

        :param sock: Socket from which the request was received
        :type sock: socket.socket
        :param req: The SIP request to be processed
        :type req: SIPRequest
        """
        not_valid = self._check_request_validly(req)
        if not_valid:
            print("not valid request!")
            self._send_to_client(sock, str(not_valid).encode())
            if not_valid.get_header('call-id'):
                with self.call_lock:
                    call_obj = self.active_calls[req.get_header('call-id')]
                    if call_obj:
                        call_obj.last_used_cseq_num += 1  # Next request expects the next cseq number
        else:
            method = req.method
            if method == SIPMethod.REGISTER.value:
                self.register_request(sock, req)  # Handle register
            elif method == SIPMethod.INVITE.value:
                self.invite_request(sock, req)  # Handle invite
            elif method == SIPMethod.ACK.value:
                print(req)
                self.ack_request(sock, req)  # Handle ACK end of invite - start RTP
            elif method == SIPMethod.BYE.value:
                pass  # Handle BYE

    def _check_request_validly(self, msg):
        """
        Validate a SIP request message for version and header completeness.

        :param msg: SIP request message
        :type msg: SIPRequest

        :return: Error response message if invalid, otherwise None
        :rtype: SIPResponse or None
        """
        status = SIPStatusCode.OK
        if msg.version != SIP_VERSION:
            status = SIPStatusCode.VERSION_NOT_SUPPORTED
            msg.version = SIP_VERSION
        if not REQUIRED_HEADERS.issubset(msg.headers):
            status = SIPStatusCode.BAD_REQUEST
            missing = REQUIRED_HEADERS - msg.headers.keys()
            for header in missing:
                msg.set_header(header, "missing")
        if msg.get_header('cseq')[1] != msg.method:
            status = SIPStatusCode.BAD_REQUEST
            msg.set_header('cseq', [msg.get_header('cseq')[0], msg.method.lower()])
        # elif len(msg.body) != msg.get_header('content-length'):
        #     error_msg.status_code = SIPStatusCode.BAD_REQUEST

        if status == SIPStatusCode.OK:
            return None
        error_msg = SIPMsgFactory.create_response_from_request(msg, status, SERVER_URI)
        return error_msg

    def bye_request(self, sock, req):
        """
        Handle a BYE SIP request to terminate an ongoing call.

        :param sock: Socket from which the request was received
        :type sock: socket.socket
        :param req: The BYE SIP request
        :type req: SIPRequest
        """
        uri_send = req.get_header('from')
        uri_recv = req.get_header('to')
        call_id = req.get_header("call-id")
        cseq = req.get_header('cseq')[0]
        with self.call_lock:  # it's better to get the lock for the whole func instead of acquiring multiple times
            # verify call details are the ok
            if call_id in self.active_calls:
                print("in call")
                call = self.active_calls[call_id]
                print(call)
                print(cseq)
                if cseq != call.last_used_cseq_num + 1 or (
                        call.uri != uri_recv and call.uri != uri_send) or call.call_type != SIPCallType.INVITE and call.call_state != SIPCallState.IN_CALL:
                    print("call invalid")
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
                call.last_active = datetime.datetime.now()

            # call valid - foward request
            send_sock = call.caller_socket if call.caller_socket == sock else call.callee_socket
            if self._send_to_client(send_sock, str(req).encode()):
                call.call_state = SIPCallState.WAITING_BYE

    def ack_request(self, sock, req):
        """
        Handle an ACK SIP request to confirm receipt of a final response to an INVITE.

        :param sock: Socket from which the request was received
        :type sock: socket.socket
        :param req: The ACK SIP request
        :type req: SIPRequest
        """
        print("starting")
        uri_recv = req.get_header('to')
        call_id = req.get_header("call-id")
        cseq = req.get_header('cseq')[0]
        # pass ack to the other side start rtp
        with self.call_lock:  # it's better to get the lock for the whole func instead of acquiring multiple times
            # verify call details are the ok
            if call_id in self.active_calls:
                print("in call")
                call = self.active_calls[call_id]
                print(call)
                print(cseq)
                if cseq != call.last_used_cseq_num + 1 or call.uri != uri_recv or call.call_type != SIPCallType.INVITE or call.caller_socket != sock:
                    print("call invalid")
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
                call.last_active = datetime.datetime.now()

                print("hello")
                print(call.call_state)
                # call is valid. now we need to check which type of ack is this
                if call.call_state == SIPCallState.WAITING_ACK:
                    print("waiting to ack")
                    # this is an invite ack - set state to in call, pass to the other side
                    call.call_state = SIPCallState.IN_CALL
                    print()
                    self._send_to_client(call.callee_socket, str(req).encode())
                elif call.call_state == SIPCallState.TRYING_CANCEL:
                    # maybe add another state for after trying

                    # this is a cancel ack - delete call
                    del self.active_calls[call_id]
        # call verified

    def cancel_request(self, sock, req):
        """
        Handle a CANCEL SIP request to terminate a pending INVITE call before it's accepted.

        :param sock: Socket from which the request was received
        :type sock: socket.socket
        :param req: The CANCEL SIP request
        :type req: SIPRequest
        """
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
                if cseq != call.last_used_cseq_num + 1 or call.uri != uri_recv or call.method != req.method or call.call_type != SIPMethod.INVITE or sock is not call.callee_socket or call.call_state != SIPCallState.RINGING:
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
                    # the call is in the correct state and can be canceled
                call.last_active = datetime.datetime.now()

            call.last_used_cseq_num = cseq
            call.last_active = datetime.datetime.now()
            # send ok response so the client knows I received. the canceling side must be the callee
            res_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.OK, SERVER_URI)
            self._send_to_client(sock, str(res_msg).encode())

            # send cancel to the other side
            req.set_header('cseq', (cseq + 1, req.get_header('cseq')[1]))
            req.set_header('from', SERVER_URI)
            if call.uri_other is not None:
                # other uri in invite is always the
                req.set_header('to', call.uri_other)
            else:
                req.set_header('to', 'cancel')

            self._send_to_client(call.caller_socket, str(req).encode())
            self.active_calls[call_id].call_state = SIPCallState.INIT_CANCEL

    def invite_request(self, sock, req):
        """
        Handle an INVITE SIP request, authenticate the sender, and initiate a call session.

        :param sock: Socket from which the request was received
        :type sock: socket.socket
        :param req: The INVITE SIP request
        :type req: SIPRequest
        """
        print("-----------------------------------------")
        print(req)
        # in register uri the uri you are trying to register
        uri_sender = req.get_header('from')
        uri_recv = req.get_header('to')
        call_id = req.get_header("call-id")
        cseq = req.get_header('cseq')[0]

        if not self.user_db.user_exists(uri_sender):
            # register is to the server only
            error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.NOT_FOUND, SERVER_URI)
            self._send_to_client(sock, str(error_msg).encode())
            return

        with self.call_lock:  # it's better to get the lock for the whole func instead of acquiring multiple times
            # verify call details are the ok
            call = None
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                if cseq != call.last_used_cseq_num + 1 or call.uri != uri_recv or call.call_type != SIPCallType.INVITE or sock is not call.caller_socket:
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
            call.last_used_cseq_num = cseq
            call.last_active = datetime.datetime.now()

            # made sure the user is auth
            # make sure we can call the callee
            is_auth = False
            user_recv = None
            with self.reg_lock:
                user_recv = self.registered_user.get_by_val(uri_recv)
                if not user_recv:
                    # can't contact callee
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.NOT_FOUND, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                    return
                # now we know who we're trying to call
                call.callee_socket = user_recv.socket
                if self.registered_user.get_by_val(uri_sender) and self.registered_user.get_by_key(sock):
                    is_auth = True
                    call.uri_other = self.registered_user.get_by_key(sock).uri  # set the other uri in the call

            if not is_auth:
                print("authing")
                auth_header = req.get_header('www-authenticate')
                if auth_header:
                    if call_id not in self.pending_auth.keys():
                        # auth request was either timed out or never sent
                        self._create_auth_challenge(sock, req)
                        return
                    # verify auth response
                    auth_header_parsed = self._parse_auth_header(auth_header)
                    if not auth_header_parsed:
                        error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST,
                                                                               SERVER_URI)
                        self._send_to_client(sock, str(error_msg).encode())
                    else:
                        password = self.user_db.get_password(uri_sender)
                        answer_now = self.authority.calculate_hash_auth(
                                                                        password,
                                                                        SIPMethod.REGISTER,
                                                                        auth_header_parsed['nonce'],
                                                                        auth_header_parsed['realm'])
                        # verify in server
                        if answer_now != auth_header_parsed['response'] or answer_now != self.pending_auth[
                            call_id].answer:
                            error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.FORBIDDEN,
                                                                                   SERVER_URI)
                            self._send_to_client(sock, str(error_msg).encode())
                            return
                else:
                    # if not authenticated
                    self._create_auth_challenge(sock, req)

            print("authd")

            # now we know the user is authenticated we can proceed to send the invite
            if call_id in self.pending_auth:
                del self.pending_auth[call_id]

            call.call_state = SIPCallState.TRYING
            if not req.body:
                error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                self._send_to_client(sock, str(error_msg).encode())
                return
            self._send_to_client(call.callee_socket, str(req).encode())
            self._send_to_client(call.caller_socket,
                                 str(SIPMsgFactory.create_response_from_request(req, SIPStatusCode.TRYING,
                                                                                SERVER_URI)).encode())

    def register_request(self, sock, req):
        """
        Handle a REGISTER SIP request to authenticate and store the user's registration.

        :param sock: Socket from which the request was received
        :type sock: socket.socket
        :param req: The REGISTER SIP request
        :type req: SIPRequest
        """
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

        if not self.user_db.user_exists(uri):
            # register is to the server only
            error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.NOT_FOUND, SERVER_URI)
            self._send_to_client(sock, str(error_msg).encode())
            return

        with self.call_lock:
            # verify call details are the ok
            call = None
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                if cseq != call.last_used_cseq_num + 1 or call.uri != uri or call.call_type != SIPCallType.REGISTER or sock is not call.caller_socket:
                    print("not standart call")
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

            call.last_used_cseq_num = cseq
            call.last_active = datetime.datetime.now()

        print(f"for {uri} checking prev")

        with self.reg_lock:
            need_auth = True
            if self.registered_user.get_by_key(sock):  # user has registered in the connection
                if self.registered_user.get_by_key(sock).uri == uri:  # the registration was for the same uri
                    # this is the same user in the same connection that was already authenticated
                    with self.reg_lock:
                        user = RegisteredUser(
                            uri=uri,
                            address=sock.getpeername(),
                            socket=sock,
                            registration_time=datetime.datetime.now(),
                            expires=expires,
                        )
                        print(user)
                        self.registered_user.add(user)  # overrides previous register if exists
                        print("registered")
                        self._send_to_client(sock, SIPMsgFactory.create_response_from_request(req, SIPStatusCode.OK,
                                                                                              SERVER_URI))

                    need_auth = False

            if self.registered_user.get_by_val(
                    uri):  # if the tries to register to a uri that is logged in but isn't him
                # someone is registered to the uri already
                error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.FORBIDDEN, SERVER_URI)
                self._send_to_client(sock, str(error_msg).encode())
                need_auth = False

            print(f"neede auth for {uri} - {need_auth}")

            if not need_auth:
                del self.active_calls[call_id]
                return

        auth_header = req.get_header('www-authenticate')
        print(f"got auth header - {bool(auth_header)}")
        if auth_header:
            with self.call_lock:
                if call_id not in self.pending_auth:
                    # auth request was either timed out or never sent
                    self._create_auth_challenge(sock, req)
                    return
                # verify auth response
                auth_header_parsed = self._parse_auth_header(auth_header)
                if not auth_header_parsed:
                    print("couldnt pass auth header")
                    error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.BAD_REQUEST, SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())
                else:
                    password = self.user_db.get_password(uri)
                    answer_now = self.authority.calculate_hash_auth(
                                                                    password,
                                                                    SIPMethod.REGISTER.value,
                                                                    auth_header_parsed['nonce'],
                                                                    auth_header_parsed['realm'])
                    # answer now based on the vars he sent

                    if answer_now != auth_header_parsed['response'] or answer_now != self.pending_auth[call_id].answer:
                        error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.FORBIDDEN, SERVER_URI)
                        self._send_to_client(sock, str(error_msg).encode())
                    else:
                        # user authenticated
                        del self.pending_auth[call_id]
                        del self.active_calls[call_id]

                        print("user authenticated")
                        with self.reg_lock:
                            # if user has previous registration delete it
                            if self.registered_user.get_by_key(sock):
                                print(f"removing prev reg: {self.registered_user.get_by_key(sock)}")
                                self.registered_user.remove_by_key(sock)
                            user = RegisteredUser(
                                uri=uri,
                                address=sock.getpeername(),
                                socket=sock,
                                registration_time=datetime.datetime.now(),
                                expires=expires,
                            )
                            self.registered_user.add(user)  # overrides previous register if exists
                            self._send_to_client(sock,
                                                 str(SIPMsgFactory.create_response_from_request(req, SIPStatusCode.OK,
                                                                                                SERVER_URI)).encode())

        else:
            print("none")
            self._create_auth_challenge(sock, req)

    def _parse_auth_header(self, header):
        """
        Parse a SIP Digest authentication header into a dictionary.

        :param header: The authentication header string
        :type header: str

        :return: Parsed authentication parameters or None if invalid
        :rtype: dict or None
        """

        # expected: Digest key="value", ...
        # must have - username, realm, nonce, response
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
        """
        Send an authentication challenge to the client.
        :param sock: Socket to send the challenge to
        :type sock: socket.socket
        :param request: Original SIP request needing authentication
        :type request: SIPRequest
        """
        # we assume the function that called us verified the user exists otherwise we store None
        method = request.method
        call_id = request.get_header('call-id')
        uri = request.get_header('from')

        # Store challenge
        with self.call_lock:
            # Generate nonce
            nonce = AuthService.generate_nonce().lower()
            password = self.user_db.get_password(uri)
            # Create challenge
            challenge = AuthChallenge(
                answer=self.authority.calculate_hash_auth(password, method, nonce, SERVER_URI),
                created_time=datetime.datetime.now()
            )
            self.pending_auth[call_id] = challenge
        print("created")

        auth_header = f'digest realm="{SERVER_URI}", nonce="{nonce}, algorithm=MD5'
        # Create challenge response
        response = SIPMsgFactory.create_response_from_request(request, SIPStatusCode.UNAUTHORIZED,
                                                              SERVER_URI, {"www-authenticate": auth_header})
        print("auth challnange is:")
        print(response)
        self._send_to_client(sock, str(response).encode())

    def process_response(self, sock, res):
        """
        Process a SIP response and perform call state transitions and validations.

        :param sock: Socket from which the response was received
        :type sock: socket.socket
        :param res: The SIP response to be processed
        :type res: SIPResponse
        """
        print(res)
        not_valid = self._check_response_valid(res)
        if not_valid:
            print(res)
            self._send_to_client(sock, str(not_valid).encode())
            return
        print("valid res")

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
                if cseq != call.last_used_cseq_num:
                    not_valid.status_code = SIPStatusCode.BAD_REQUEST
                    self._send_to_client(sock, str(not_valid).encode())
                    return
                call.last_active = datetime.datetime.now()

        if call_id in self.pending_keep_alive:
            with self.conn_lock:
                # The response is to a keep alive
                if res.status_code is SIPStatusCode.OK and res.get_header('cseq')[0] == self.pending_keep_alive[
                    call_id].last_used_cseq_num:
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

                    elif call.call_state == SIPCallState.RINGING and res.status_code == SIPStatusCode.DECLINE:
                        print("call declined!")
                        with self.call_lock:
                            del self.active_calls[
                                call_id]  # the call was declined, remove call send decline to other side
                    elif call.call_state == SIPCallState.RINGING and res.status_code == SIPStatusCode.OK:
                        call.call_state = SIPCallState.WAITING_ACK
                        if not res.body:
                            print("not valid!")
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
                        # del self.active_calls[call_id] - do it in the ack
                    elif call.call_state == SIPCallState.WAITING_BYE and res.status_code == SIPStatusCode.OK:
                        # delete call
                        with self.call_lock:
                            del self.active_calls[call_id]

                    else:
                        not_valid.status_code = SIPStatusCode.NOT_ACCEPTABLE
                        self._send_to_client(sock, str(not_valid).encode())
                        return  # we do not want to foward thhe invalid msg

                    # forward to other side
                    send_sock = call.caller_socket if sock != call.caller_socket else call.callee_socket
                    self._send_to_client(send_sock, str(res).encode())
                else:
                    # if the call was not an invite then it is not possible to send response
                    error_msg = SIPMsgFactory.create_response_from_request(res, SIPStatusCode.NOT_ACCEPTABLE_ANYWHERE,
                                                                           SERVER_URI)
                    self._send_to_client(sock, str(error_msg).encode())

    def _check_response_valid(self, msg):
        """
        Validate a SIP response message for version and required headers.

        :param msg: SIP response message
        :type msg: SIPResponse

        :return: Error response message if invalid, otherwise None
        :rtype: SIPResponse or None
        """
        status = SIPStatusCode.OK
        if msg.version != SIP_VERSION:
            status = SIPStatusCode.VERSION_NOT_SUPPORTED
            msg.version = SIP_VERSION
        if not REQUIRED_HEADERS.issubset(msg.headers):
            status = SIPStatusCode.BAD_REQUEST
            missing = REQUIRED_HEADERS - msg.headers.keys()
            for header in missing:
                msg.set_header(header, "missing")
        if msg.status_code not in SIPStatusCode:
            status = SIPStatusCode.BAD_REQUEST

        # elif len(msg.body) != msg.get_header('content-length'):
        #     error_msg.status_code = SIPStatusCode.BAD_REQUEST
        error_msg = SIPMsgFactory.create_response(status, SIP_VERSION,
                                                  SIPMethod.OPTIONS,
                                                  msg.get_header('cseq')[0],
                                                  msg.get_header('from'),
                                                  SERVER_URI,
                                                  msg.get_header('call-id')
                                                  )
        if error_msg.status_code == SIPStatusCode.OK:
            return None
        return error_msg

    def _cleanup_expired_reg(self):
        while self.running:
            """Removes registrations that are past expiration"""
            with self.reg_lock:
                for uri, user in self.registered_user.val_to_obj:
                    if (datetime.datetime.now() - user.registration_time) >= user.expires:
                        self.registered_user.remove_by_val(uri)
            time.sleep(30)

    def _cleanup_inactive_calls(self):
        while self.running:
            """Removes calls with sockets that are inactive"""
            with self.call_lock:
                for call_id, call in self.active_calls:
                    if (
                            datetime.datetime.now() - call.last_active) >= CALL_IDLE_LIMIT and call.call_type != SIPCallState.IN_CALL:

                        # send to the clients that the call was terminated if active
                        end_msg = SIPMsgFactory.create_response(SIPStatusCode.DOES_NOT_EXIST_ANYWHERE, SIP_VERSION,
                                                                SIPMethod.OPTIONS,
                                                                SIPMethod.INVITE, 'none', SERVER_URI, call.call_id)
                        send_sock = call.caller_socket
                        if self.registered_user.get_by_key(send_sock):
                            end_msg.set_header('to', self.registered_user.get_by_key(send_sock))
                        self._send_to_client(send_sock, str(end_msg).encode())
                        del self.active_calls[call_id]

                        send_sock = call.callee_socket
                        if send_sock != self.server_socket:
                            if self.registered_user.get_by_key(send_sock):
                                end_msg.set_header('to', self.registered_user.get_by_key(send_sock))
                            else:
                                end_msg.set_header('to', 'none')
                            self._send_to_client(send_sock, str(end_msg).encode())

                            del self.active_calls[call_id]

                        # if the call was register then we need to remove the invalid auth challenge
                        if call.uri in self.pending_auth:
                            del self.pending_auth[call.uri]
            time.sleep(30)

    def _cleanup_ip_counters(self):
        """
        Periodically cleans up IP tracking dicts to prevent memory overflow.
        """
        while self.running:
            now = time.time()
            with self.ip_lock:
                for ip_dict in [self.ip_connection_counts, self.ip_message_counts]:
                    inactive_ips = []
                    for key, value in ip_dict.items():
                        ip_dict[key] = [t for t in value if now - t < self.time_window]
                        if not ip_dict[key]:
                            inactive_ips.append(key)
                    for key in inactive_ips:
                        del ip_dict[key]
            time.sleep(60)

    def _keep_alive(self):
        """
        Send periodic keep-alive SIP messages and remove unresponsive clients.
        """
        while self.running:
            with self.conn_lock:
                for call_id, keep_alive in list(self.pending_keep_alive.items()):
                    # Socket should be in connected users. Check for safety
                    if keep_alive.client_socket in self.connected_users:
                        del self.pending_keep_alive[call_id]
                        self._close_connection(keep_alive.client_socket)
                # Everyone that remained has answered the keep alive
                for sock in self.connected_users:
                    msg = KEEP_ALIVE_MSG
                    call_id = generate_random_call_id()
                    msg.set_header('call-id', call_id)
                    print(f"sending: {msg}")
                    self._send_to_client(sock, str(msg).encode())
                    keep_alive_obj = KeepAlive(call_id, 1, sock)
                    self.pending_keep_alive[call_id] = keep_alive_obj
            time.sleep(30)

    def _close_connection(self, sock):
        """
        Close a client connection and clean up all associated state (users, calls, etc.).

        :param sock: The socket to be closed
        :type sock: socket.socket
        """
        print("closing connection!")
        with self.conn_lock:
            if sock in self.connected_users:
                self.connected_users.remove(sock)
                # pending_keep_alive entry would be removed by the _keep_alive func
        with self.reg_lock:
            self.registered_user.remove_by_key(sock)

        with self.ip_lock:
            if sock in self.ip_message_counts:
                # do not clean ip. may be more than one connection. this is for the CONNECTION
                del self.ip_message_counts[sock] # if he has pending msgs which he probably has then clean his entry
        with self.call_lock:
            end_msg = None
            # Remove a call that the sock is in. If there is another UAC send them an error msg
            for call_id, call in list(self.active_calls.items()):
                if call.caller_socket is sock or call.callee_socket is sock:
                    if call.call_type == SIPCallType.INVITE:
                        print("adawd")
                        send_sock = call.caller_socket if call.callee_socket == sock else call.callee_socket
                        with self.reg_lock:
                            if self.registered_user.get_by_key(send_sock):
                                to_uri = self.registered_user.get_by_key(send_sock).uri
                                end_msg = SIPMsgFactory.create_response(SIPStatusCode.DOES_NOT_EXIST_ANYWHERE,
                                                                        SIP_VERSION,
                                                                        SIPMethod.OPTIONS, call.last_used_cseq_num,
                                                                        to_uri, SERVER_URI, call.call_id)

                    if call.uri in self.pending_auth:
                        del self.pending_auth[call.uri]
                    del self.active_calls[call_id]
                    if end_msg:
                        print(end_msg)
                        self._send_to_client(send_sock, str(end_msg).encode())


        sock.close()

    def _send_to_client(self, sock, data):
        """
        Send data to a client over TCP. Close the connection on failure.

        :param sock: Socket to send data through
        :type sock: socket.socket
        :param data: Byte data to be sent
        :type data: bytes
        """
        if not send_sip_tcp(sock, data):
            print("couldnt send")
            self._close_connection(sock)


"""
for each call have a state so you know if the msgs send are valid for the state. 
have diuffernt thred for srt. send commands through queue.
"""

server = SIPServer()
server.start()
