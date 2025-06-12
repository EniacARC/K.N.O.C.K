from utils.authentication import *
from mediator_connect import ControllerAware
import socket

from utils.comms import recv_encrypted, send_encrypted
from utils.encryption.aes import AESCryptGCM
from utils.encryption.rsa import RSACrypt

SERVER_URI = "myserver"
SERVER_IP = '127.0.0.1'
SERVER_PORT = 2433

SUCCESS_RESPONSE = "SIGNUP"
class SignupClient(ControllerAware):
    def __init__(self):
        super().__init__()
        # self.controller = mediator
        self.socket = None
        self.server_ip = SERVER_IP
        self.server_port = SERVER_PORT
        self.aes_obj = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(3) # don't want to hold up gui
            self.socket.connect((self.server_ip, self.server_port))
            print(f"Connected to signup server {self.server_ip}:{self.server_port}")
            return self.key_exchange()
        except socket.error as e:
            print(f"Connection failed: {e}")
            return False
    def key_exchange(self):
        self.aes_obj = AESCryptGCM()
        rsa = RSACrypt()
        rsa_key = recv_encrypted(self.socket)
        if rsa_key != b'':
            # print('--------------------')
            # print(f"rsa key client: {rsa_key}")
            # print('--------------------')
            rsa.import_public_key(rsa_key)
            enc_data = rsa.encrypt(self.aes_obj.export_key())
            print(f'client:\n{self.aes_obj.export_key()}')
            # print(f"encoded: {enc_data}")
            send_encrypted(self.socket, enc_data)
            return True
        return False

    # def signup(self, username, password):

    # maybe in a thread??
    def signup(self, username, password):
        if not self.connect():
            return False, "Couldn't connect to signup server"

        ha1 = calculate_ha1(username, password, SERVER_URI)
        signup_msg = username + '|' + ha1
        signup_msg_enc = self.aes_obj.encrypt(signup_msg.encode())
        if send_encrypted(self.socket, signup_msg_enc):
            response = recv_encrypted(self.socket)
            print(response)
            if response:
                response_str = self.aes_obj.decrypt(response).decode()
                if response_str == SUCCESS_RESPONSE:
                    return True, "Signup Successful"
                else:
                    return False, "Signup Failed"

        return False, "something went wrong while signing up!"