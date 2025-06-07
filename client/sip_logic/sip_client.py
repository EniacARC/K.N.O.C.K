import socket
import threading
from dataclasses import dataclass
from typing import Optional

import select

from utils.comms import receive_tcp_sip, send_sip_tcp
from utils.sip_msgs import *
from utils.authentication import *
from utils.sdp_class import *
from client.mediator_connect import *
SERVER_IP = '127.0.0.1'
SERVER_PORT = 4552
SIP_VERSION = "SIP/2.0"
SERVER_URI = "myserver"
MAX_PASSES_META = 8000  # 8 kb
MAX_PASSES_BODY = 1000


@dataclass
class Call:  # For both invite and register
    call_type: SIPCallType
    call_id: str
    remote_uri: str
    call_state: SIPCallState
    last_used_cseq_num: int
    call_data: Optional[object] = None

class SIPHandler(ControllerAware):
    def __init__(self, username, password):
        super().__init__()
        self.uri = username
        self.password = password
        self.server_ip = SERVER_IP
        self.server_port = SERVER_PORT
        self.socket = None
        self.connected = False

        # self.current_call_id = None
        # self.call_type = None
        # self.call_state = None
        self.call = None

        self.auth_authority = AuthService(SERVER_URI)
        self.lingering_data = None

    def connect(self):
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
        if self.connected:
            self.socket.close()
            print("Disconnected from server")

    def start(self):
        threading.Thread(target=self._main_loop).start()

    def _main_loop(self):
        if not self.connected:
            return
        while self.connected:
            readable, _, _ = select.select([self.socket], [], [], 0.5)
            for sock in readable:
                msg = receive_tcp_sip(sock, MAX_PASSES_META, MAX_PASSES_BODY)
                print(f"{self.uri} recvd: {msg}")

                if isinstance(msg, SIPRequest):
                    self._handle_request(msg)
                elif msg.get_header('call-id') == self.call.current_call_id:
                    self.process_response(msg)

    def _handle_request(self, msg):
        method = msg.method

        if method == SIPMethod.OPTIONS.value:
            self._handle_options(msg)
        elif method == SIPMethod.INVITE.value:
            self._handle_invite(msg)
        elif msg.get_header('call-id') == self.call.current_call_id:
            self.process_request(msg)

    def _handle_options(self, msg):
        res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, self.uri)
        send_sip_tcp(self.socket, str(res).encode())

    def _handle_invite(self, msg):
        if self.call:
            res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.DECLINE, self.uri)
            send_sip_tcp(self.socket, str(res).encode())
        else:
            self.call = Call(
                call_type=SIPCallType.INVITE,
                call_id=msg.get_header('call-id'),
                remote_uri=msg.get_header('from'),
                call_state=SIPCallState.RINGING,
                last_used_cseq_num=msg.get_header('cseq')[0],

            )
            self.process_invite(msg)

    def process_request(self, msg):
        if self.call.call_type != SIPCallType.INVITE:
            raise Exception("Unexpected message for current call type")

        if msg.method == SIPMethod.CANCEL.value:
            self.process_cancel(msg)
        elif msg.method == SIPMethod.ACK.value:
            self.process_ack(msg)
        elif msg.method == SIPMethod.BYE.value:
            self.process_bye(msg)

    def answer_call(self, answer_call):
        if self.call.call_state != SIPCallState.RINGING:
            print("The call has changed its state")
            return

        if answer_call:
            self.call.call_state = SIPCallState.WAITING_ACK
            self._handle_call_acceptance()
        else:
            res = SIPMsgFactory.create_response_from_request(self.lingering_data, SIPStatusCode.DECLINE, self.uri)
            send_sip_tcp(self.socket, str(res).encode())
            self.clear_call()

        self.lingering_data = None

    def _handle_call_acceptance(self):
        sdp_recv = SDP.parse(self.lingering_data.body)
        if not sdp_recv:
            return

        self.controller.set_remote_ip(sdp_recv.ip)
        if sdp_recv.audio_port:
            self.controller.set_send_audio(sdp_recv.audio_port)
        if sdp_recv.video_port:
            self.controller.set_send_video(sdp_recv.video_port)

        self.controller.set_recv_ports(video=True, audio=True)

        local_sdp = SDP(0, '127.0.0.1', sdp_recv.session_id,
                        video_port=self.controller.get_recv_video_port(), video_format='h.264',
                        audio_port=self.controller.get_recv_audio_port(), audio_format='acc')

        res = SIPMsgFactory.create_response_from_request(
            self.lingering_data, SIPStatusCode.OK, self.uri, body=str(local_sdp))
        send_sip_tcp(self.socket, str(res).encode())

    def process_invite(self, msg):
        res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.RINGING, self.uri)
        if send_sip_tcp(self.socket, str(res).encode()):
            self.call.call_data = msg

    def process_cancel(self, msg):
        if self.call.call_state == SIPCallState.RINGING:
            res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, self.uri)
            if send_sip_tcp(self.socket, str(res).encode()):
                res.status_code = SIPStatusCode.REQUEST_TERMINATED
                if send_sip_tcp(self.socket, str(res).encode()):
                    self.call.call_state = SIPCallState.TRYING_CANCEL

    def process_ack(self, msg):
        if self.call.call_state == SIPCallState.TRYING_CANCEL:
            self.clear_call()
        else:
            self.controller.start_stream()

    def process_bye(self, msg):
        res = SIPMsgFactory.create_response_from_request(msg, SIPStatusCode.OK, self.uri)
        send_sip_tcp(self.socket, str(res).encode())
        self.clear_call()

    def send_auth_response(self, msg):
        print("auth")
        method = SIPMethod.INVITE if self.call.call_type == SIPCallType.INVITE else SIPMethod.REGISTER
        cseq = msg.get_header('cseq')[0] + 1
        self.call.last_used_cseq_num += 1
        fields = self._parse_auth_request(msg.get_header('www-authenticate'))

        if fields['algorithm'] != 'md5':
            self.clear_call()
            return

        response = self.auth_authority.calculate_hash_auth(
            self.password, method.value, fields['nonce'], fields['realm'])

        auth_header = f'digest username="{self.uri}", realm="{fields["realm"]}", ' \
                      f'nonce="{fields["nonce"]}", response="{response}"'

        req = SIPMsgFactory.create_request(method, SIP_VERSION, msg.get_header('from'),
                                           msg.get_header('to'), self.call.current_call_id, cseq,
                                           {'www-authenticate': auth_header})
        send_sip_tcp(self.socket, str(req).encode())

    def _parse_auth_request(self, header):
        if not header or not header.lower().startswith("digest "):
            return None

        header = header[7:].strip()
        pattern = re.compile(r'(\w+)=([\"\']?)([^\"\',]+)\2')
        parsed = {match[0]: match[2].strip() for match in pattern.findall(header)}

        required_fields = ['realm', 'nonce', 'algorithm']
        if not all(field in parsed for field in required_fields):
            return None
        return parsed

    def process_response(self, msg):
        """
        Process a SIP response message

        :param msg: the SIP response message
        :type msg: SIPResponse
        """
        status = msg.status_code

        # Authentication handling
        if self.call.call_state == SIPCallState.WAITING_AUTH and status == SIPStatusCode.UNAUTHORIZED:
            self.send_auth_response(msg)
            return

        # Call rejected or registration failed
        if status == SIPStatusCode.DOES_NOT_EXIST_ANYWHERE:
            self.clear_call()
            return

        # Handle REGISTER responses
        if self.call.call_type == SIPCallType.REGISTER:
            if status == SIPStatusCode.OK:
                self.clear_call()
            else:
                self.controller.response_for_login(status.value)
            return

        # Handle INVITE responses
        if self.call.call_type == SIPCallType.INVITE:
            if self.call.call_state is None and status == SIPStatusCode.TRYING:
                self.call.call_state = SIPCallState.TRYING

            elif self.call.call_state == SIPCallState.TRYING and status == SIPStatusCode.RINGING:
                print("ringing")
                self.call.call_state = SIPCallState.RINGING

            elif self.call.call_state == SIPCallState.RINGING:
                if status == SIPStatusCode.DECLINE:
                    self.clear_call()
                elif status == SIPStatusCode.OK:
                    print("okay")
                    sdp_recv = SDP.parse(msg.body)
                    print("recvd")
                    print(sdp_recv)
                    if sdp_recv:
                        self.controller.set_remote_ip(sdp_recv.ip)
                        if sdp_recv.audio_port:
                            self.controller.set_send_audio(sdp_recv.audio_port)
                        if sdp_recv.video_port:
                            self.controller.set_send_video(sdp_recv.video_port)

                        cseq = msg.get_header('cseq')[0] + 1
                        self.call.last_used_cseq_num = cseq
                        ack = SIPMsgFactory.create_request(
                            SIPMethod.ACK,
                            SIP_VERSION,
                            msg.get_header('from'),
                            self.uri,
                            self.call.current_call_id,
                            cseq
                        )


                        print(f"acking: {ack}")
                        if send_sip_tcp(self.socket, str(ack).encode()):
                            self.call_state = SIPCallState.IN_CALL
                            print("start stream - send")
                            self.controller.start_stream()
            return

        # Handle CANCEL responses
        if self.call.call_state == SIPCallState.INIT_CANCEL and status == SIPStatusCode.OK:
            self.call.call_state = SIPCallState.TRYING_CANCEL

        elif self.call.call_state == SIPCallState.TRYING and status == SIPStatusCode.REQUEST_TERMINATED:
            cseq = msg.get_header('cseq')[0] + 1
            self.call.last_used_cseq_num = cseq
            ack = SIPMsgFactory.create_request(
                SIPMethod.ACK,
                SIP_VERSION,
                SERVER_URI,
                self.uri,
                self.call.current_call_id,
                cseq
            )
            send_sip_tcp(self.socket, str(ack).encode())
            self.clear_call()

    def register(self):

        self.call = Call(
            call_type=SIPCallType.REGISTER,
            call_id=generate_random_call_id(),
            remote_uri=SERVER_URI,
            call_state=SIPCallState.WAITING_AUTH,
            last_used_cseq_num=1
        )

        req = SIPMsgFactory.create_request(SIPMethod.REGISTER, SIP_VERSION, SERVER_URI, self.uri, self.call.call_id, self.call.last_used_cseq_num)
        send_sip_tcp(self.socket, str(req).encode())

    def invite(self, uri):

        self.call = Call(
            call_type=SIPCallType.INVITE,
            call_id=generate_random_call_id(),
            remote_uri=uri,
            call_state=SIPCallState.WAITING_AUTH,
            last_used_cseq_num=1
        )

        session_id = SDP.generate_session_id()

        self.controller.set_recv_ports(video=True, audio=True)
        sdp_body = SDP(0, '127.0.0.1', session_id,
                       video_port=self.controller.get_recv_video_port(), video_format='h.264',
                       audio_port=self.controller.get_recv_audio_port(), audio_format='acc')

        req = SIPMsgFactory.create_request(SIPMethod.INVITE, SIP_VERSION, uri, self.uri, self.call.call_id, self.call.last_used_cseq_num, body=str(sdp_body))
        send_sip_tcp(self.socket, str(req).encode())

    def bye(self):
        self.call.last_used_cseq_num += 1
        req = SIPMsgFactory.create_request(SIPMethod.BYE,
                                           SIP_VERSION,
                                           self.call.remote_uri,
                                           self.uri,
                                           self.call.call_id,
                                           self.call.last_used_cseq_num)
        self.call.call_state = SIPCallState.WAITING_BYE
        send_sip_tcp(self.socket, str(req).encode())

    def cancel(self):
        self.call.last_used_cseq_num += 1
        req = SIPMsgFactory.create_request(SIPMethod.CANCEL,
                                           SIP_VERSION,
                                           self.call.remote_uri,
                                           self.uri,
                                           self.call.call_id,
                                           self.call.last_used_cseq_num)
        self.call.call_state = SIPCallState.INIT_CANCEL
        send_sip_tcp(self.socket, str(req).encode())

    def clear_call(self):
        print(f"Terminating call {self.call.current_call_id}")
        self.call = None
        self.lingering_data = None
        self.controller.clear_rtp_ports()
