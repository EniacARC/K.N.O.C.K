import datetime


class ClientState:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.connection_time = datetime.datetime.now()
