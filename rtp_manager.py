import random
import socket


class RTPManager:
    def __init__(self):
        self.used_ports = []

        # remote ports
        self.send_audio = None
        self.send_video = None

        # my ports
        self.recv_audio = None
        self.recv_video = None

    def allocate_port(self):
        for _ in range(100):
            port = random.randint(10000, 60000)
            if port not in self.used_ports and self._is_port_free(port):
                self.used_ports.append(port)
                return port
        raise RuntimeError("Failed to allocate free port")

    def _is_port_free(self, port):
        """Checks if a port is free by trying to bind a UDP socket."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind(('0.0.0.0', port))
                return True
            except OSError:
                return False

    def set_send_audio(self, audio):
        self.send_audio = audio

    def set_send_video(self, video):
        self.send_video = video

    def set_recv_ports(self, video=False, audio=False):
        if audio:
            self.recv_audio = self.allocate_port()
        if video:
            self.recv_video = self.allocate_port()

    def clear_ports(self):
        self.used_ports = []
        self.send_audio = None
        self.send_video = None
        self.recv_audio = None
        self.recv_video = None
