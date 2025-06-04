import socket
import struct

from utils.sip_msgs import *

INT_SIZE = 4
PACK_SIGN = "I"


def send_tcp(sock, data):
    """
    Send data over a TCP socket.

    :param sock: The TCP socket.
    :type sock: socket.socket
    :param data: The data to be sent.
    :type data: bytes

    :return: None
    """
    length = struct.pack(PACK_SIGN, socket.htonl(len(data)))
    to_send = length + data
    try:
        sent = 0
        while sent < len(to_send):
            sent += sock.send(to_send[sent:])
        return True
    except socket.error as err:
        print(f"error while sending at: {err}")
        return False


def send_sip_tcp(sock, data):
    """
    Send data over a TCP socket.

    :param sock: The TCP socket.
    :type sock: socket.socket
    :param data: The data to be sent.
    :type data: bytes

    :return: None
    """
    try:
        sent = 0
        while sent < len(data):
            sent += sock.send(data[sent:])
        print("sent all")
        return True
    except socket.error as err:
        print(f"error while sending at: {err}")
        return False


def receive_tcp(sock):
    """
    Receive data over a TCP socket.

    :param sock: The TCP socket.
    :type sock: socket.socket

    :return: The received data.
    :rtype: bytes
    """
    try:
        length = 0
        buf = b''
        data_len = b''
        data = b''

        while len(data_len) < INT_SIZE:
            buf = sock.recv(INT_SIZE - len(data_len))
            if buf == b'':
                data_len = b''
                break
            data_len += buf

        if data_len != b'':
            length = socket.htonl(struct.unpack(PACK_SIGN, data_len)[0])

        while len(data) < length:
            buf = sock.recv(length - len(data))
            if buf == b'':
                data = b''
                break
            data += buf
        return data

    except socket.timeout:
        return b''

    except socket.error as err:
        # print(f"error while recv: {err}")
        return b''


def recv_sip_metadata(sock, max_passes):
    """
     receive metadata from the server

     :param sock: the socket for communication
     :type sock: socket.socket

     :return: received metadata
     :rtype: str
     """
    client_request = ""
    passes = 0
    try:
        while not re.search('\r\n\r\n', client_request) and passes < max_passes:
            passes += 1
            packet = sock.recv(1).decode()
            if packet == '':
                client_request = ''
                break
            client_request += packet
    except socket.error as err:
        # logging.error(f"error while recv metadata: {err}")
        client_request = ''
    finally:
        return client_request


def recv_sip_body(sock, num, max_passes):
    """
     receive a constant-sized message from the server

     :param sock: the socket for communication
     :type sock: socket.socket

     :param num: the size of the message to receive
     :type num: int

     :return: received message
     :rtype: bytes
     """
    bod = ''
    passes = 0
    try:
        while len(bod) < num and passes < max_passes:
            passes += 1
            chunk = sock.recv(num - len(bod)).decode()
            if chunk == '':
                bod = ''
                break
            bod += chunk
    except socket.error as err:
        # logging.error(f"error while recv body: {err}")
        bod = ''
    finally:
        return bod


def receive_tcp_sip(sock, max_passes_metadata, max_passes_body):
    """
    Receive and parse a SIP message

    This function first reads the SIP metadata from the socket, parses it into a SIP message,
    and if a `Content-Length` header is present and non-zero, it reads the corresponding body as well.

    :param sock: the TCP socket to receive data from
    :type sock: socket.socket

    :param max_passes_metadata: maximum number of read attempts for the SIP metadata
    :type max_passes_metadata: int

    :param max_passes_body: maximum number of read attempts for the SIP body
    :type max_passes_body: int

    :return: parsed SIP message if successful, otherwise None
    :rtype: SIPMessage or None
    """
    metadata = recv_sip_metadata(sock, max_passes_metadata)
    sip_msg = SIPMsgFactory.parse(metadata)
    if sip_msg:
        if sip_msg.get_header('content-length') is not None and sip_msg.get_header('content-length') != 0:
            sip_msg.body = recv_sip_body(sock, sip_msg.get_header('content-length'), max_passes_body)
            if len(sip_msg.body) == sip_msg.get_header('content-length'):
                return sip_msg
        else:
            return sip_msg
    return None
