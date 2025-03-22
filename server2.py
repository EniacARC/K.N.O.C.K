from comms import *
from sip_msgs import *

# server constants
SERVER_IP = '127.0.0.1'
SERVER_PORT = 2022
SERVER_QUEUE_SIZE = 1
SERVER_NAME = "ChapalServer"

SIP_VERSION = 'SIP/2.0'
WWW_AUTH = f'Digest algorithm=MD5,realm="yonatan.realm",nonce='


def is_auth(username):
    return True
def user_exists(username):
    return True
def generate_nonce():
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    random_part = ''.join(random.choices(characters, k=16))  # Generate random string
    timestamp = int(time.time())  # Current UNIX timestamp
    return f"{timestamp}-{random_part}"  # Combine timestamp and random part

def get_password_ha1(username):
    return 'fsedfe'

def calculate_hash_auth(nonce, username):
    ha1 = get_password_ha1(username)
    ha2 = hashlib.md5(f"REGISTER:{SERVER_NAME}")
    return hashlib.md5(f"{ha1}:{nonce}:{ha2}")

def handle_register(sock, reg_obj):
    if not user_exists(req_obj.get_header('from')):
        error_res = SIPMsgFactory.create_response(reg_obj, SIPStatusCode.NOT_FOUND)
        send_tcp(sock, str(error_msg))
        return False
    if not is_auth(req_obj.get_header('from')):
        nonce = generate_nonce()
        extra_headers = {"WWW_Authenticate", WWW_AUTH+f'"{nonce}"'}
        unauth_res = SIPMsgFactory.create_response(reg_obj, SIPStatusCode.UNAUTHORIZED, extra_headers)
        if not send_tcp(sock, str(unauth_res)):
            return False

        replay_msg = receive_tcp(sock)
        if not replay_msg:
            return False
        replay_obj = SIPMsgFactory.parse(replay_msg) # check None

        if replay_obj.get_header('cseq')[0] != reg_obj.get_header('cseq')[0] + 1 or replay_obj.get_header('Authorization') is None:
            error_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_msg))
            return False
        response = re.search(r'response="([^"]+)"', replay_obj.get_header('Authorization'))
        if not response:
            error_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_msg))
            return False
        response = response.group(1)
        if response != calculate_hash_auth(nonce, reg_obj.get_header('from')):
            error_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.NOT_ACCEPTABLE)
            send_tcp(sock, str(error_msg))
            return False
        ok_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.OK)
        send_tcp(sock, str(ok_res))
        # add registration to db
        return True




def handle_sip_request(sock, req_obj):
    if req_obj.method == SIPMethod.REGISTER:
        handle_register(sock, req_obj)

def handle_client(sock, addr):
    # aes_key = rsa_exchange(sock, addr) #create obj(?)
    while True:
        raw_msg = receive_tcp(sock)
        if not raw_msg:
            break
        msg_obj = SIPMsgFactory.parse(raw_msg)
        if not msg_obj:
            break

        if SIPMsg.is_request(raw_msg):
            handle_sip_request(sock, msg_obj)


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
