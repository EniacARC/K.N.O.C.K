"""
sip server:
need to use thread pool that is PER MSG
no need for registration for invite - needs validation if not registered
pools communicate through CALLS - this is the way thread pools have context

for every response - send to the other side. maybe send something back to the sender
everytime you return - if sdp then change ports and save for the rtp call


register - register and add to endpoints, meaning people that you can CALL TO.
registered users are allowed to be contacted, and don't need extra validation

cleanup thread that closes inactive calls, expired reg
(maybe make reg persistent)

for requests - need auth.
for response no need for auth

AUTH:
you send auth challenge. the uac send a NEW request back with auth (including all params needed to calculate).
the server saves ha1 not plaintext.

auth using DIGEST ------ maybe switch to kerberos??? (talk about it)

I have a call class


for keep_alive use OPTIONS
send every 10 seconds. every time i receive add to a list. if not on the list remove
"""
import concurrent.futures

import sip_msgs
from sip_msgs import *
import socket
import datetime
import threading
import time
from dataclasses import dataclass
from enum import Enum

from comms import *

import select

DEFAULT_SERVER_PORT = 5040
MAX_WORKERS = 10
SIP_VERSION = "SIP/2.0"
SERVER_URI = "myserver"
KEEP_ALIVE_LIMIT = 60 * 5
CALL_IDLE_LIMIT = 15
REQUIRED_HEADERS = {'to', 'from', 'call-id', 'cseq', 'content-length'}
KEEP_ALIVE_MSG = SIPMsgFactory.create_request(sip_msgs.SIPMethod.OPTIONS, SIP_VERSION, "keep-alive", "keep-alive",
                                              "", "1")


@dataclass
class RegisteredUser:
    """ struct for registered user"""
    uri: str
    address: (str, int)
    socket: socket.socket
    registration_time: datetime.time
    expires: int  # amnt of sec


# dataclasses for storing session info for each msg type
@dataclass
class Call: # for both invite and register
    call_type: SIPCallType
    call_id: str
    uri: str # either caller or callee depending on call type
    callee_socket: socket.socket
    caller_socket = socket.socket
    call_state: SIPCallState
    last_used_cseq_num: int
    last_active: datetime.datetime


@dataclass
class KeepAlive:
    # kept alive is for connection - not for registered uacs, so it's socket context
    call_id: str
    last_used_cseq_num: int
    client_socket: socket.socket


# non-optimal lookup
# @dataclass
# class Socket:
#     sock: socket.socket
#     creation_time: datetime.time

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
        # socket props
        self.host = '0.0.0.0'
        self.port = port
        self.server_socket = None
        self.running = False
        self.queue_len = 5

        # thread pool props
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="sip_worker"
        )

        # locks - rlock for multiple aqrs in the same thread
        self.reg_lock = threading.RLock()  # lock for adding users to the registered_users dict
        self.call_lock = threading.RLock()  # lock for adding users to the active_calls dict
        self.conn_lock = threading.RLock()

        # user management props
        # self.socket_to_uri = {} # maybe add in the future
        self.registered_user = BiMap(key_attr="socket", value_attr="uri")

        self.active_calls = BiMap(key_attr="socket", value_attr="call_id")
        
        # maybe switch to socket -> socket heartbeat object(?)
        self.connected_users = []  # sockets
        self.pending_keep_alive = {}  # call-id -> KeepAlive
        # self.kept_alive_round = []

        # add auth object

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.running = True
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.queue_len)

            # clean any expired regs or inactive users
            cleanup_thread = threading.Thread(target=self._cleanup_expired_reg, daemon=True)
            keepalive_thread = threading.Thread(target=self._keep_alive, daemon=True)
            cleanup_thread.start()
            keepalive_thread.start()

            # start server loop
            while self.running:
                with self.conn_lock:
                    readable, _, _ = select.select(self.connected_users + [self.server_socket], [], [],
                                                   0.5)
                for sock in readable:
                    if sock is self.server_socket:
                        # incoming connection
                        client_sock, addr = self.server_socket.accept()
                        # check if ip blacklisted
                        # add addr to table. if too many entries in a short amount of time then DOS block IP.
                        with self.conn_lock:
                            self.connected_users.append(client_sock)
                            # self.kept_alive_round.append(client_sock)
                    else:
                        msg = receive_tcp(sock)
                        if msg:
                            self.thread_pool.submit(self._worker_process_msg, sock, msg)
                        else:
                            self._close_connection(sock)
        except socket.error as err:
            print(err + "something went wrong!")
            # stop func
        finally:
            self.running = False
            with self.conn_lock:
                while self.connected_users:
                    self.connected_users.pop().close()
            self.server_socket.close()

    def _worker_process_msg(self, sock, msg):
        sip_msg = SIPMsgFactory.parse(msg.decode())
        if not sip_msg:
            print("error! invalid sip msg - cannot respond")
            return

        if isinstance(sip_msg, SIPRequest):
            self.process_request(sock, sip_msg)
        else:
            self.process_request(sock, sip_msg)

    def process_request(self, sock, req):
        not_valid = self._check_request_validly(req)
        if not_valid:
            if not send_tcp(sock, str(not_valid).encode()):
                self._close_connection(sock)
            if not_valid.get_header('call-id'):
                with self.call_lock:
                    call_obj = self.active_calls.get_by_val(req.get_header('call-id'))
                    if call_obj:
                        call_obj.last_used_cseq_num += 1 # next request expects the next cseq number
        else:
            method = req.method
            if method == SIPMethod.REGISTER:
                pass  # handle register
            elif method == SIPMethod.INVITE:
                pass  # handle invite
            elif method == SIPMethod.ACK:
                pass  # handle ack end of invite - start rtp
            elif method == SIPMethod.BYE:
                pass  # handle BYE

    def _check_request_validly(self, msg):
        error_msg = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK)
        if msg.version != SIP_VERSION:
            error_msg.status_code = SIPStatusCode.VERSION_NOT_SUPPORTED
            error_msg.version = SIP_VERSION
        if REQUIRED_HEADERS.issubset(msg.headers):
            error_msg.status_code = SIPStatusCode.BAD_REQUEST
            missing = REQUIRED_HEADERS - msg.headers.keys()
            for header in missing:
                error_msg.set_header(header, "missing")
        if msg.get_header['cseq'][1] != msg.method.lower():
            error_msg.status_code = SIPStatusCode.BAD_REQUEST
            error_msg.set_header('cseq', [msg.get_header['cseq'][0], msg.method.lower()])

        if error_msg.status_code == SIPStatusCode.OK:
            return None
        return error_msg

    def register_request(self, sock, req):
        # doesn't check if the two requests are equal
        # uri = req.get_header("from")
        # with self.reg_lock:
        #     if self.registered_user.get_user(uri):
        #         error_msg = SIPMsgFactory.create_response_from_request(req, SIPStatusCode.NOT_ACCEPTABLE)
        #         send_tcp(sock, str(error_msg).encode())


    def invite_request(self):
        pass
        # -----------------------------------------------------

    def process_response(self, sock, res):
        not_valid = self._check_response_valid(res)
        if not_valid:
            if not send_tcp(sock, not_valid):
                self._close_connection(sock)
        call_id = res.get_header('call-id')
        if call_id in self.pending_keep_alive:
            with self.conn_lock:
                # the response is to a keep alive
                if res.status_code is SIPStatusCode.OK and res.get_header('cseq') == str(
                        self.pending_keep_alive[call_id].last_used_cseq_num):
                    del self.pending_keep_alive[call_id]  # the response was valid so the connection is kept alive
                # else response is invalid, and we drop them at the next keep_alive check
        else:
            # if not keep alive then it's for an invite call
            pass
    def _check_response_valid(self, msg):
        error_msg = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK)
        if msg.version != SIP_VERSION:
            error_msg.status_code = SIPStatusCode.VERSION_NOT_SUPPORTED
            error_msg.version = SIP_VERSION
        if REQUIRED_HEADERS.issubset(msg.headers):
            error_msg.status_code = SIPStatusCode.BAD_REQUEST
            missing = REQUIRED_HEADERS - msg.headers.keys()
            for header in missing:
                error_msg.set_header(header, "missing")
        if msg.status_code not in SIPStatusCode:
            error_msg.status_code = SIPStatusCode.BAD_REQUEST

        if error_msg.status_code == SIPStatusCode.OK:
            return None
        return error_msg

    def _cleanup_expired_reg(self):
        """removes registrations that are past expiration"""
        with self.reg_lock:
            for uri, user in self.registered_user.val_to_obj:
                if (datetime.datetime.now() - user.registration_time) >= user.expires:
                    self.registered_user.remove_by_val(uri)
        time.sleep(30)
        
    def _cleanup_inactive_calls(self):
        """removes calls with sockets that """
        with self.call_lock:
            for call_id, call in self.active_calls.val_to_obj:
                if (datetime.datetime.now() - call.last_active) >= CALL_IDLE_LIMIT:
                    self.active_calls.remove_by_val(call_id)
        time.sleep(30)
    def _keep_alive(self):
        while self.running:
            """send heartbeats. if socket didn't respond to the last heartbeat then he is inactive """
            with self.conn_lock:
                for call_id, keep_alive in self.pending_keep_alive.items():
                    # socket should be in connected users. check for safety
                    if keep_alive.client_socket in self.connected_users:
                        del self.pending_keep_alive[call_id]
                        self._close_connection(keep_alive.client_socket)
                # everyone that remained has answered teh keep alive
                for sock in self.connected_users:
                    msg = KEEP_ALIVE_MSG
                    call_id = generate_random_call_id()
                    msg.set_header('call-id', call_id)

                    if not send_tcp(sock, str(msg).encode()):
                        self._close_connection(sock)
                        continue
                    keep_alive_obj = KeepAlive(call_id, 1, sock)
                    self.pending_keep_alive[call_id] = keep_alive_obj
            time.sleep(30)

    def _close_connection(self, sock):
        """remove user from both active_users and registered_users when applicable"""
        with self.conn_lock:
            if sock in self.connected_users:
                self.connected_users.remove(sock)
                # pending_keep_alive entry would be removed by the _keep_alive func
        with self.reg_lock:
            self.registered_user.remove_by_key(sock)
        with self.conn_lock:
            # remove a call that the sock is in. if there is another uac send them an error msg
            call = self.active_calls.get_by_key(sock)
            if call:
                call_obj = self.active_calls.get_by_val(call)
                if call_obj.call_type is SIPCallType.INVITE:
                    # if invite the other side deserves a msg
                    send_sock = call_obj.caller_socket if call_obj.callee_socket == sock else call_obj.callee_socket
                    to_uri, _ = send_sock.getpeername()
                    with self.reg_lock:
                        if self.registered_user.get_by_key(send_sock):
                            to_uri = self.registered_user.get_by_key(send_sock)
                    end_msg = SIPMsgFactory.create_response(SIPStatusCode.NOT_FOUND, SIP_VERSION, SIPMethod.INVITE, to_uri, SERVER_URI, call)
                    self.active_calls.remove_by_key(sock)  # if one of the sockets is removed the call ends
                    if not send_tcp(send_sock, str(end_msg).encode()):
                        self._close_connection(send_sock)
        sock.close()

# close
# # Close all active connections
# with self.conn_lock:
#     for conn in list(self.active_connections):
#         try:
#             conn.close()
#         except:
#             pass
#     self.active_connections.clear()
#
# # Close server socket
# if self.server_socket:
#     self.server_socket.close()
