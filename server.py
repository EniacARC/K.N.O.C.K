import socket
import threading

# server constants
SERVER_IP = '127.0.0.1'
SERVER_PORT = 2022
SERVER_QUEUE_SIZE = 1

def handle_client(sock, addr):
        aes_key = rsa_exchange(sock, addr) #create obj(?)
        register_user_sip() #registers +/ adds to connected clients

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
