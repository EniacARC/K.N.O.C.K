import socket
import threading

from utils.comms import send_encrypted, recv_encrypted
from utils.encryption.aes import AESCryptGCM
from utils.encryption.rsa import RSACrypt
from utils.user_database import UserDatabase

SERVER_URI = "myserver"
SERVER_SIGNUP_PORT = 2433
DB_PATH = '../utils/users.db'
MAX_CLIENTS = 5
CLIENT_SEMAPHORE = threading.Semaphore(MAX_CLIENTS)
SUCCESS_RESPONSE = "SIGNUP"


class SignupServer:
    def __init__(self, port=SERVER_SIGNUP_PORT):
        self.server_socket = None
        self.port = port
        self.host = '0.0.0.0'
        self.queue_len = 5
        self.user_db = UserDatabase(DB_PATH)
        self.lock = CLIENT_SEMAPHORE

        self.rsa_crypt = RSACrypt()
        self.rsa_crypt.generate_keys()
        self.public_key = self.rsa_crypt.export_public_key() # bytes

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.queue_len)
            print(f"listening on {self.host}:{self.port}")
            while True:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(5) # if client doesn't respond fast we want disconnect him to prevent hogging resources
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
        except socket.error and KeyboardInterrupt as err:
            print("ERROR")
            print(err)
        finally:
            self.server_socket.close()

    def handle_client(self, sock):
        self.lock.acquire()
        # print('--------------------')
        # print(f"rsa key server: {self.public_key}")
        # print('--------------------')
        send_encrypted(sock, self.public_key)
        rsa_encrypted = recv_encrypted(sock)
        if rsa_encrypted != b'':
            aes_key = self.rsa_crypt.decrypt(rsa_encrypted)
            encrypt_obj = AESCryptGCM(aes_key)
            print(f'server:\n{aes_key}')

            signup_msg_enc = recv_encrypted(sock)
            if signup_msg_enc:
                signup_msg = encrypt_obj.decrypt(signup_msg_enc).decode()
                signup_split = signup_msg.split('|')
                if len(signup_split) == 2:
                    # testing doesn't work for password need to find fix
                    if self.user_db.add_user(signup_split[0], signup_split[1]):
                        print("success")
                        enc_msg = encrypt_obj.encrypt(SUCCESS_RESPONSE.encode())
                        print(enc_msg)
                        print(encrypt_obj.decrypt(enc_msg).decode())
                        send_encrypted(sock, enc_msg)
                    else:
                        enc_msg = encrypt_obj.encrypt("Signup Failed".encode())
                        send_encrypted(sock, enc_msg)
                else:
                    enc_msg = encrypt_obj.encrypt("NOT VALID FORMAT".encode())
                    send_encrypted(sock, enc_msg)

        self.lock.release()
        sock.close()

if __name__ == '__main__':
    serv = SignupServer()
    serv.start()