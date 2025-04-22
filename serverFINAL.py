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
KEEP_ALIVE_LIMIT = 60 * 5
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


@dataclass
class Call:
    call_id: str
    caller_uri: str
    callee_uri: str
    call_state: str
    last_used_cseq_num: int
    start_time: datetime.datetime


@dataclass
class KeepAlive:
    call_id: str
    last_used_cseq_num: int
    client_socket: socket.socket


# non-optimal lookup
# @dataclass
# class Socket:
#     sock: socket.socket
#     creation_time: datetime.time

class RegistrationMap:
    def __init__(self):
        self.uri_to_user = {}
        self.socket_to_uri = {}

    def add(self, user):
        """user = RegisteredUser instance"""
        self.uri_to_user[user.uri] = user
        self.socket_to_uri[user.socket] = user.uri

    def remove_by_socket(self, sock):
        if sock in self.socket_to_uri:
            uri = self.socket_to_uri[sock]
            del self.socket_to_uri[sock]
            del self.uri_to_user[uri]
            return True
        return False

    def remove_by_uri(self, uri):
        if uri in self.uri_to_user:
            user = self.socket_to_uri[uri]
            del self.socket_to_uri[user.socket]
            del self.uri_to_user[uri]
            return True
        return False

    def get_user(self, uri):
        return self.uri_to_user[uri] if uri in self.uri_to_user else None

    def get_uri(self, sock):
        return self.socket_to_uri[sock] if sock in self.socket_to_uri else None


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
        self.registered_user = RegistrationMap()

        self.active_calls = {}  # call-id: str -> Call

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
        method = req.method
        if method == SIPMethod.REGISTER:
            pass  # handle register
        elif method == SIPMethod.INVITE:
            pass  # handle invite
        elif method == SIPMethod.ACK:
            pass  # handle ack end of invite - start rtp
        elif method == SIPMethod.BYE:
            pass  # handle BYE

    def process_response(self, res):
        pass

    def _cleanup_expired_reg(self):
        """removes registrations that are past expiration"""
        with self.reg_lock:
            for uri, user in self.registered_user.uri_to_user:
                if (datetime.datetime.now() - user.registration_time) >= user.expires:
                    self.registered_user.remove_by_uri(uri)
        time.sleep(60)

    def _keep_alive(self):
        while self.running:
            """send heartbeats. if socket didn't respond to the last heartbeat then he is inactive """
            with self.conn_lock:
                for call_id, keep_alive in self.pending_keep_alive:
                    # socket should be in connected users. check for safety
                    if keep_alive.client_socket in self.connected_users:
                        del self.pending_keep_alive[call_id]
                        self._close_connection(keep_alive.client_socket)
                # everyone that remained has answered teh keep alive
                for sock, _ in self.connected_users:
                    msg = KEEP_ALIVE_MSG
                    call_id = generate_random_call_id()
                    msg.set_header('call-id', call_id)

                    if not send_tcp(sock, str(msg).encode()):
                        self._close_connection(sock)
                        continue
                    keep_alive_obj = KeepAlive(call_id, 1, sock)
                    self.pending_keep_alive[call_id] = keep_alive_obj
            time.sleep(10)

    def _close_connection(self, sock):
        """remove user from both active_users and registered_users when applicable"""
        with self.conn_lock:
            if sock in self.connected_users:
                self.connected_users.remove(sock)
                # pending_keep_alive entry would be removed by the _keep_alive func
        with self.reg_lock:
            self.registered_user.remove_by_socket(sock)
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
