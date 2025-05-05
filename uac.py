import socket
import time

from sip_msgs import *
from comms import *
from sdp_class import *

SERVER_IP = '127.0.0.1'
SERVER_PORT = 4552
SIP_VERSION = "SIP/2.0"
SERVER_URI = "myserver"


class SIPClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.server_ip = SERVER_IP
        self.server_port = SERVER_PORT
        self.socket = None
        self.connected = False

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

    def register(self):
        if not self.connected:
            return
        reg_msg = SIPMsgFactory.create_request(SIPMethod.REGISTER, SIP_VERSION, SERVER_URI, "myuri", "123", 1)
        print("reg msg")
        print(reg_msg.get_header('cseq'))
        # Send initial REGISTER request
        print("Sending REGISTER request...")
        if send_sip_tcp(self.socket, str(reg_msg).encode()):
            msg_challenge = receive_tcp_sip(self.socket, 8000, 32000)
            print("got back:")
            print(msg_challenge)
            if msg_challenge:
                reg_msg.get_header('cseq')[0] += 1
                auth_header = 'Digest username="a1", realm="test1", nonce="hello", response="1234"'
                reg_msg.set_header("WWW-Authenticate", auth_header)
                print(reg_msg)
                if send_sip_tcp(self.socket, str(reg_msg).encode()):
                    print("end")
                    msg_ok = receive_tcp_sip(self.socket, 8000, 32000)
                    print("got back:")
                    print(msg_ok)
                    time.sleep(30)



client = SIPClient("1", "2")
client.connect()
client.register()
# client.disconnect()