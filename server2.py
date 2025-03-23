import hashlib
import string
from datetime import time
import random

from comms import *
from sip_msgs import *

# server constants
SERVER_IP = '127.0.0.1'
SERVER_PORT = 2022
SERVER_QUEUE_SIZE = 1
SERVER_NAME = "ChapalServer"

SIP_VERSION = 'SIP/2.0'
WWW_AUTH = f'Digest algorithm=MD5,realm="yonatan.realm",nonce='

USER_DB = {
    'alice': {'password_ha1': hashlib.md5('alice:yonatan.realm:password123'.encode()).hexdigest(), 'ip': None,
              'port': None},
    'bob': {'password_ha1': hashlib.md5('bob:yonatan.realm:securepass'.encode()).hexdigest(), 'ip': None, 'port': None}
}

# Active calls tracking
active_calls = {}


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
    if not user_exists(reg_obj.get_header('from')):
        error_res = SIPMsgFactory.create_response(reg_obj, SIPStatusCode.NOT_FOUND)
        send_tcp(sock, str(error_res).encode())
        return False
    if not is_auth(reg_obj.get_header('from')):
        nonce = generate_nonce()
        extra_headers = {"WWW_Authenticate", WWW_AUTH + f'"{nonce}"'}
        unauth_res = SIPMsgFactory.create_response(reg_obj, SIPStatusCode.UNAUTHORIZED, extra_headers)
        if not send_tcp(sock, str(unauth_res).encode()):
            return False

        replay_msg = receive_tcp(sock)
        if not replay_msg:
            return False
        replay_obj = SIPMsgFactory.parse(replay_msg)  # check None

        if replay_obj.get_header('cseq')[0] != reg_obj.get_header('cseq')[0] + 1 or replay_obj.get_header(
                'Authorization') is None:
            error_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_res).encode())
            return False
        response = re.search(r'response="([^"]+)"', replay_obj.get_header('Authorization'))
        if not response:
            error_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_res).encode())
            return False
        response = response.group(1)
        if response != calculate_hash_auth(nonce, reg_obj.get_header('from')):
            error_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.NOT_ACCEPTABLE)
            send_tcp(sock, str(error_res).encode())
            return False
        ok_res = SIPMsgFactory.create_response(replay_obj, SIPStatusCode.OK)
        send_tcp(sock, str(ok_res).encode())
    # add registration to db
    return True


def handle_invite(sock, inv_obj):
    """
    Handle SIP INVITE requests for call initiation.

    This function processes incoming INVITE requests, authenticates users,
    forwards the call setup to the callee, and manages the call session.

    Args:
        sock: The socket connected to the caller
        inv_obj: The parsed SIP INVITE message object

    Returns:
        bool: True if the INVITE was processed successfully, False otherwise
    """
    try:
        print("Processing INVITE request")

        # 1. Extract and validate caller and callee information
        from_header = inv_obj.get_header('from')
        to_header = inv_obj.get_header('to')

        if not from_header or not to_header:
            print("Missing From or To header")
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_res).encode())
            return False

        caller_match = re.search(r'sip:([^@]+)@([^:>]+)(?::(\d+))?', from_header)
        callee_match = re.search(r'sip:([^@]+)@([^:>]+)(?::(\d+))?', to_header)

        if not caller_match or not callee_match:
            print("Invalid From or To header format")
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_res).encode())
            return False

        caller_username = caller_match.group(1)
        caller_domain = caller_match.group(2)
        caller_port = caller_match.group(3) or "5060"

        callee_username = callee_match.group(1)
        callee_domain = callee_match.group(2)
        callee_port = callee_match.group(3) or "5060"

        print(f"Call request: {caller_username}@{caller_domain} -> {callee_username}@{callee_domain}")

        # 2. Verify both users exist in our system
        if not user_exists(caller_username):
            print(f"Caller {caller_username} not found")
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.NOT_FOUND)
            send_tcp(sock, str(error_res).encode())
            return False

        if not user_exists(callee_username):
            print(f"Callee {callee_username} not found")
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.NOT_FOUND)
            send_tcp(sock, str(error_res).encode())
            return False

        # 3. Check if caller is authenticated
        if not is_auth(caller_username):
            print(f"Caller {caller_username} not authenticated")
            nonce = generate_nonce()
            extra_headers = {"WWW-Authenticate": WWW_AUTH + f'"{nonce}"'}
            unauth_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.UNAUTHORIZED, extra_headers)
            send_tcp(sock, str(unauth_res).encode())
            return False

        # 4. Check if callee is registered and available
        if not USER_DB[callee_username]['ip'] or not USER_DB[callee_username]['port']:
            print(f"Callee {callee_username} not registered or unavailable")
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.BAD_REQUEST)
            send_tcp(sock, str(error_res).encode())
            return False

        # 5. Send TRYING response back to caller (100 Trying)
        print("Sending 100 Trying response")
        trying_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.TRYING)
        if not send_tcp(sock, str(trying_res).encode()):
            print("Failed to send TRYING response")
            return False

        # 6. Extract and validate Call-ID
        call_id = inv_obj.get_header('call-id')
        if not call_id:
            print("Missing Call-ID, generating one")
            call_id = f"{random.randint(1000000, 9999999)}@{SERVER_IP}"

        # 7. Check for existing call with this Call-ID
        if call_id in active_calls:
            print(f"Call with ID {call_id} already exists")
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.SERVICE_UNAVAILABLE)
            send_tcp(sock, str(error_res).encode())
            return False

        sdp_content = inv_obj.body
        content_type = inv_obj.get_header('content-type')

        callee_ip = USER_DB[callee_username]['ip']
        callee_port = USER_DB[callee_username]['port']

        # forward invite to callee

        print(f"Would forward INVITE to {callee_username} at {callee_ip}:{callee_port}")

        print("Sending 180 Ringing response")
        ringing_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.RINGING)
        if not send_tcp(sock, str(ringing_res).encode()):
            print("Failed to send RINGING response")
            return False

        print("Waiting for callee to answer...")

        local_media_port = random.randint(10000, 20000)
        server_tag = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        sdp_body = (
            "v=0\r\n"
            f"o={SERVER_NAME} {random.randint(1000, 9999)} {random.randint(1000, 9999)} IN IP4 {SERVER_IP}\r\n"
            "s=SIP Call Session\r\n"
            f"c=IN IP4 {callee_ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {local_media_port} RTP/AVP 0 8 101\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
            "a=rtpmap:8 PCMA/8000\r\n"
            "a=rtpmap:101 telephone-event/8000\r\n"
            "a=sendrecv\r\n"
        )

        print("Sending 200 OK response")
        extra_headers = {
            "Content-Type": "application/sdp",
            "Content-Length": str(len(sdp_body)),
            "Contact": f"<sip:{callee_username}@{callee_ip}:{callee_port}>",
            "To": f"{to_header};tag={server_tag}"  # Add tag to To header
        }

        ok_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.OK, extra_headers, sdp_body)
        if not send_tcp(sock, str(ok_res).encode()):
            print("Failed to send OK response")
            return False

        # 14. Wait for ACK from caller
        print("Waiting for ACK from caller...")
        # In a real implementation, we would wait for an ACK message here
        # For now, we'll assume it's received successfully

        # 15. Add this call to active calls
        print(f"Adding call {call_id} to active calls")
        active_calls[call_id] = {
            'caller': {
                'username': caller_username,
                'ip': caller_domain,
                'port': int(caller_port),
                'socket': sock
            },
            'callee': {
                'username': callee_username,
                'ip': callee_ip,
                'port': int(callee_port),
                'socket': None  # In real implementation, this would be the socket to the callee
            },
            'start_time': time.time(),
            'status': 'connected',
            'media': {
                'caller_port': None,  # Would be extracted from caller's SDP
                'callee_port': local_media_port
            }
        }

        print(f"Call {call_id} established successfully")
        return True

    except Exception as e:
        print(f"Error in handle_invite: {e}")
        try:
            error_res = SIPMsgFactory.create_response(inv_obj, SIPStatusCode.SERVER_ERROR)
            send_tcp(sock, str(error_res).encode())
        except:
            print("Failed to send error response")
        return False


def handle_sip_request(sock, req_obj):
    if req_obj.method == SIPMethod.REGISTER:
        return handle_register(sock, req_obj)
    elif req_obj.method == SIPMethod.INVITE:
        return handle_invite(sock, req_obj)


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
            if is_auth(msg_obj.get_header('from')):
                handle_sip_request(sock, msg_obj)
            else:
                handle_register(sock, re)


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
