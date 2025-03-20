import socket
import string
import threading
import time
import hashlib

from comms import *
from sip import SIPRequest, SIPResponse, SIPMsgFactory, SIPMsg
import random

# server constants
SERVER_IP = '127.0.0.1'
SERVER_PORT = 2022
SERVER_QUEUE_SIZE = 1
SERVER_NAME = "ChapalServer"

SIP_VERSION = 'SIP/2.0'
WWW_AUTH = f'Digest algorithm=MD5,realm="yonatan.realm",nonce='

def validate_sip_msg(msg, method, required_headers):
    if msg.method != method:
        return False
    elif msg.version != SIP_VERSION:
        return False
    elif [i for i, j in zip(required_headers, msg.headers.keys()) if i == j] != required_headers:
        return False

def check_if_user_exists(name):
    return True

def generate_nonce():
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    random_part = ''.join(random.choices(characters, k=16))  # Generate random string
    timestamp = int(time.time())  # Current UNIX timestamp
    return f"{timestamp}-{random_part}"  # Combine timestamp and random part
def get_password_ha1(username):
    return 'fsedfe'

def calculate_hash(nonce, username):
    ha1 = get_password_ha1(username)
    ha2 = hashlib.md5(f"REGISTER:{SERVER_NAME}")
    return hashlib.md5(f"{ha1}:{nonce}:{ha2}")

def register_user(sock):
    reg_req_raw = receive_tcp(sock)
    if not reg_req_raw:
        return False
    reg_req = SIPMsgFactory.parse(False, reg_req_raw)
    if not validate_sip_msg(reg_req, 'REGISTER', ['to', 'from', 'call-id', 'cseq']):
        # send_tcp(sock, SIPResponse('400 Bad Request', SIP_VERSION).build_msg().encode())
        return False
    if reg_req.uri != 'sip:' + SERVER_NAME or 'REGISTER' not in reg_req.headers['cseq']:
        # send_tcp(sock, SIPResponse('400 Bad Request', SIP_VERSION).build_msg().encode())
        return False

    username = reg_req.headers['to'][1:-2].replace('sip:', 'None')
    call_id = reg_req.headers['call-id']
    cseq = SIPMsg.get_cseq(reg_req.headers['cseq'])
    if not check_if_user_exists(username):
        # send_tcp(sock, SIPResponse('404 Not Found', SIP_VERSION).build_msg().encode())
        return False



    nonce = generate_nonce()
    unauth_res = SIPResponse('401 Unauthorised', SIP_VERSION)
    unauth_res.set_header('to', reg_req.headers['to'])
    unauth_res.set_header('from', reg_req.headers['from'])
    unauth_res.set_header('call-id', call_id)
    unauth_res.set_header('cseq', reg_req.headers['cseq'])
    unauth_res.set_header('WWW_Authenticate', WWW_AUTH+f'"{nonce}"')
    send_tcp(sock, unauth_res.build_msg().encode())

    reg_req_auth_raw = receive_tcp(sock)
    if not reg_req_auth_raw:
        return False

    reg_auth = SIPMsgFactory.parse(False, reg_req_raw)

    if not validate_sip_msg(reg_auth, 'REGISTER', ['to', 'from', 'call-id', 'cseq', 'response']):
        # send_tcp(sock, SIPResponse('400 Bad Request', SIP_VERSION).build_msg().encode())
        return False
    if reg_auth.uri != 'sip:' + SERVER_NAME or 'REGISTER' not in reg_auth.headers['cseq'] or SIPMsg.get_cseq(reg_auth.headers['cseq']) != cseq + 1:
        # send_tcp(sock, SIPResponse('400 Bad Request', SIP_VERSION).build_msg().encode())
        return False
    if reg_auth.headers['response'] != calculate_hash(nonce, username):
        # send_tcp(sock, SIPResponse('400 Bad Request', SIP_VERSION).build_msg().encode())
        return False
    return True


def handle_client(sock, addr):
        aes_key = rsa_exchange(sock, addr) #create obj(?)
        register_user() #registers +/ adds to connected clients

        #sip loop
        while not in rtp:
            msg = aes_decrypt(aes_key, recv_msg(sock))
            extract_data(msg)

        if(rtp):
            start_rtp_session(sock)

        sip_bye()

        sock.close()


def main():
    """
    The main functions. Runs the server code.

    return: none
    """
    # define sockets for server
    server_socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        # set up tcp sockets for incoming connections
        server_socket_tcp.bind((SERVER_IP, SERVER_PORT))
        server_socket_tcp.listen(SERVER_QUEUE_SIZE)


        while True:
            client_socket, client_addr = server_socket_tcp.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))
    except socket.error as err:
        print("something went wrong! please restart server!")
    finally:
        server_socket_tcp.close()
        server_socket_udp.close()
