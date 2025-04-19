import time
import threading
from socket import socket


class SIPEndpoint:
    def __init__(self, uri, addr_ip, addr_port, expires):
        self.uri = uri
        self.ip = addr_ip
        self.port = addr_port
        self.expires = expires
        self.last_seen = time.time()

    def is_expired(self):
        return (time.time() - self.last_seen) > self.expires

    def compare(self, other_ip, other_port):
        return self.ip == other_ip and self.port == other_port

class SIPCall:
    def __init__(self, call_id, from_uri, to_uri):
        self.call_id = call_id
        self.from_uri = from_uri
        self.to_uri = to_uri
        self.start_time = None

    def start_call(self):
        self.start_time = time.time()

    def get_call_duration(self):
        return time.time() - self.start_time


class SIPServer:
    """this is the sip server only. no rtp proxy logic"""
    def __init__(self, ip, port, queue_size):
        self.ip = ip
        self.port = port
        self.queue_size = queue_size
        self.socket = None
        self.endpoints = {}
        self.calls = {}
        self.lock = threading.Lock()
        self.running = False

    def handle_connection(self):
        pass
    def start(self):
        """start the sip server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True
        try:
            self.socket.bind((self.ip, self.port))
            self.socket.listen(self.queue_size)
        while self.running:
            client_socket, client_addr = self.socket.accept()
            threading.Thread
    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

"""
sip server functionality:
runs on tcp
for each user must register!
authenticate only through th register
use keep alive!

invite - use pools to send msgs to the correct uri
        


functionality:
register: maps uri to addr
invite: establishes call between two endpoints
"""