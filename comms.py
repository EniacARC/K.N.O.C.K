import socket
import struct

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
