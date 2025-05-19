import socket
import threading

import select
from abc import ABC, abstractmethod

from comms import receive_tcp_sip, send_sip_tcp
from sip_msgs import *
from authentication import *
SERVER_IP = '127.0.0.1'
SERVER_PORT = 4552
SIP_VERSION = "SIP/2.0"
SERVER_URI = "myserver"
MAX_PASSES_META = 8000  # 8 kb
MAX_PASSES_BODY = 1000


# class CallObserver(ABC):
#     @abstractmethod
#     def terminate_call(self, call_id: str): pass
#
#     @abstractmethod
#     def allocate_port(self): pass
#
# class CallHandler:
#     def __init__(self, sock, uri, call_id, call_type, observer: CallObserver):
#         self.sock = sock
#         self.uri = uri
#         self.call_id = call_id
#         self.call_type = call_type
#         self.observer = observer
#         self.state = None
#
#     def process_response(self, msg):
#         pass
#
#     def process_request(self, msg):
#         # if i process a request it must be an invite type
#         if self.call_type != SIPCallType.INVITE:
#             raise Exception("unexpected msg for call")
#         if msg.method == SIPMethod.INVITE:
#             self.process_invite(msg)
#         elif msg.method == SIPMethod.CANCEL:
#             self.process_cancel(msg)
#         elif msg.method == SIPMethod.ACK:
#             self.process_ack(msg)
#
#     def process_invite(self, msg):
#         answer = input(f"Do you accept call from {msg.get_header('from')}? Y/N") # integrate into gui
#         if answer == 'Y':
#             # process sdp
#             res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.RINGING, self.uri)
#             if send_sip_tcp(self.sock, str(res).encode()):
#                 self.state = SIPCallState.RINGING
#             # what if it didn't work?
#     def process_cancel(self, msg):
#         if self.state == SIPCallState.RINGING:
#             res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, self.uri)
#             if send_sip_tcp(self.sock, str(res).encode()):
#                 res.status_code = SIPStatusCode.REQUEST_TERMINATED
#                 if send_sip_tcp(self.sock, str(res).encode()):
#                     self.state = SIPCallState.TRYING_CANCEL
#
#     def process_ack(self, msg):
#         if self.state == SIPCallState.TRYING_CANCEL:
#             # this is the last cancel need to remove object
#             self.observer.terminate_call(self.call_id)
#         elif self.state




class SIPHandler:
    def __init__(self, username, password):
        self.uri = username
        self.password = password
        self.server_ip = SERVER_IP
        self.server_port = SERVER_PORT
        self.socket = None
        self.connected = False

        # self.calls = {} # call_id callObj

        # Only one call at a time
        self.current_call_id = None
        self.call_type = None
        self.call_state = None

        self.auth_authority = AuthService(SERVER_URI)


    def connect(self):
        """Establish connection to the SIP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.server_port))
            print(f"Connected to server {self.server_ip}:{self.server_port}")
            self.connected = True
            return True
        except socket.error as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close connection to the SIP server"""
        if self.connected:
            self.socket.close()
            print("Disconnected from server")

    def start(self):
        main_loop = threading.Thread(target=self._main_loop)
        main_loop.start()
    def _main_loop(self):
        if not self.connected:
            return
        while self.connected:
            readable, _, _ = select.select([self.socket], [], [], 0.5)
            for sock in readable:
                msg = receive_tcp_sip(sock, MAX_PASSES_META, MAX_PASSES_BODY)
                print(msg)
                if isinstance(msg, SIPRequest):
                    if msg.method == SIPMethod.OPTIONS.value:
                        # keep alive
                        res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, self.uri)
                        send_sip_tcp(self.socket, str(res).encode())

                    elif msg.method == SIPMethod.INVITE.value:
                        if self.current_call_id is not None:
                            # Already in call, reject new
                            res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.DECLINE, self.uri)
                            send_sip_tcp(self.socket, str(res).encode())
                        else:
                            # Accept new call
                            self.current_call_id = msg.get_header('call-id')
                            self.call_type = SIPCallType.INVITE
                            self.call_state = None
                            self.process_invite(msg)

                    elif msg.get_header('call-id') == self.current_call_id:
                        self.process_request(msg)

                    else:
                        # Unknown call-id and not INVITE, ignore or handle as needed
                        pass

                else:
                    # It's a response, must belong to current call
                    if msg.get_header('call-id') == self.current_call_id:
                        self.process_response(msg)

    def process_request(self, msg):
        # Only one call supported, so just handle requests for current call
        if self.call_type != SIPCallType.INVITE:
            raise Exception("unexpected message for current call type")

        if msg.method == SIPMethod.CANCEL.value:
            self.process_cancel(msg)
        elif msg.method == SIPMethod.ACK.value:
            self.process_ack(msg)
        elif msg.method == SIPMethod.BYE.value:
            self.process_bye(msg)

    def answer_call(self, msg, answer_call):
        # answer = input(f"Do you accept call from {who}? Y/N ")
        # if by the time we answer we get a cancel request then we will be able to process it, the server will return an error msg
        if self.call_state == SIPCallState.RINGING: # we might get a cancel request in the meantime
            if answer_call:
                self.call_state = SIPCallState.WAITING_ACK
            # Further processing of SDP or call setup can go here
            # get sdp of other
            # build my sdp
            # send sdp in 200ok
            else:
                # Reject call
                res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.DECLINE, self.uri)
                send_sip_tcp(self.socket, str(res).encode())
                self.clear_call()
        else:
            print("The call has changed it's state")
    def process_invite(self, msg):
        # Accept call
        res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.RINGING, self.uri)
        if send_sip_tcp(self.socket, str(res).encode()):
            self.call_state = SIPCallState.RINGING
            self.answer_call(msg, True)
            # call gui for answer (using event, not blocking main thread for recv)

    def process_cancel(self, msg):
        if self.call_state == SIPCallState.RINGING:
            res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, self.uri)
            if send_sip_tcp(self.socket, str(res).encode()):
                res.status_code = SIPStatusCode.REQUEST_TERMINATED
                if send_sip_tcp(self.socket, str(res).encode()):
                    self.call_state = SIPCallState.TRYING_CANCEL

    def process_ack(self, msg):
        if self.call_state == SIPCallState.TRYING_CANCEL:
            # Cancel completed, clear call
            self.clear_call()
        else:
            # Normal ACK handling here
            pass

    def _parse_auth_request(self, header):
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
        required_fields = ['realm', 'nonce', 'algorithm']
        if not all(field in parsed for field in required_fields):
            return None

        return parsed
    def send_auth_response(self, msg):
        if self.call_type == SIPCallType.INVITE:
            method = SIPMethod.INVITE
        else:
            method = SIPMethod.REGISTER

        cseq = msg.get_header('cseq')[0] + 1
        fields = self._parse_auth_request(msg.get_header('www-authenticate'))
        algo = fields['algorithm']
        nonce = fields['nonce']
        realm = fields['realm']
        if algo != 'md5':
            # not valid
            self.clear_call()
        else:
            response = self.auth_authority.calculate_hash_auth(self.uri, method.value, nonce, realm)

            auth_header = f'digest username="{self.uri}", realm="{realm}", nonce="{nonce}", response="{response}"'

            req = SIPMsgFactory.create_request(method,
                                           SIP_VERSION,
                                           msg.get_header('from'),
                                           msg.get_header('to'),
                                           self.current_call_id,
                                           cseq,
                                               {'www-authenticate': auth_header})

            send_sip_tcp(self.socket, str(req).encode())

    def process_response(self, msg):
        # Process responses for current call if needed
        if self.call_state == SIPCallState.WAITING_AUTH and msg.status_code == SIPStatusCode.UNAUTHORIZED:
            # we need to send auth response
            self.send_auth_response(msg)
        elif self.call_type == SIPCallType.REGISTER:
              if msg.status_code == SIPStatusCode.OK:
                # register was successful
                self.clear_call()
        elif self.call_type == SIPCallType.INVITE:
            if msg.status_code == SIPStatusCode.TRYING:
                self.call_state = SIPStatusCode.TRYING
            elif self.call_state == SIPCallState.TRYING and msg.status_code == SIPStatusCode.RINGING:
                self.call_state = SIPCallState.RINGING
            elif self.call_state == SIPCallState.RINGING and msg.status_code == SIPStatusCode.OK:
                self.call_state = SIPCallState.IN_CALL
                # start rtp call

            # cancel responses
            elif self.call_state == SIPCallState.INIT_CANCEL and msg.status_code == SIPStatusCode.OK:
                self.call_type = SIPCallState.TRYING_CANCEL
            elif self.call_state == SIPCallState.TRYING and msg.status_code == SIPStatusCode.REQUEST_TERMINATED:
                # send ack to the server for the cancel
                cseq = msg.get_header('cseq')[0]+1
                res = SIPMsgFactory.create_request(SIPMethod.ACK, SIP_VERSION, SERVER_URI, self.uri, self.current_call_id, cseq=cseq)
                send_sip_tcp(self.socket, str(res).encode())
                self.clear_call()

        elif msg.status_code == SIPStatusCode.DOES_NOT_EXIST_ANYWHERE:
            # the call was terminated in the server
            self.clear_call()


    def register(self):
        req = SIPMsgFactory.create_request(SIPMethod.REGISTER, SIP_VERSION, SERVER_URI, self.uri, "1233", 1)
        self.current_call_id = "1233"
        self.call_type = SIPCallType.REGISTER
        self.call_state = SIPCallState.WAITING_AUTH
        send_sip_tcp(hand.socket, str(req).encode())

    def invite(self):
        req = SIPMsgFactory.create_request(SIPMethod.INVITE, SIP_VERSION, 'user2', self.uri, "456", 1, body="hello")
        self.current_call_id = "456"
        self.call_type = SIPCallType.INVITE
        send_sip_tcp(self.socket, str(req).encode())


    def clear_call(self):
        print(f"Terminating call {self.current_call_id}")
        self.current_call_id = None
        self.call_type = None
        self.call_state = None

        # if we have rtp then close it

    def allocate_port(self):
        pass

hand = SIPHandler('user1', 'qwe')
hand.connect()
hand.start()
hand.register()
hand.invite()
