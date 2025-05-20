import random
import socket
import threading
from queue import Queue

from mediator import ControllerAware
from rtp_handler import RTPHandler
from audio_capture import AudioHandler
from RTP_msgs import RTPPacket

class RTPManager(ControllerAware):
    def __init__(self):

        super().__init__()
        self.used_ports = []

        # remote ports
        self.send_ip = None
        self.send_audio = None
        self.send_video = None

        # my ports
        self.recv_audio = None
        self.recv_video = None

        self.running = False

        self.recv_audio_queue = Queue.queue() # (timestamp, frame)
        self.recv_video_queue = Queue.queue() # (timestamp, frame)
        # rtp handler objects

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

    def set_ip(self, ip):
        self.send_ip = ip
    def set_send_audio(self, audio):
        if self.send_ip:
            self.send_audio = audio

    def set_send_video(self, video):
        if self.send_ip:
            self.send_video = video

    def set_recv_ports(self, video=False, audio=False):
        if audio:
            self.recv_audio = self.allocate_port()
        if video:
            self.recv_video = self.allocate_port()

    def get_recv_audio(self):
        return self.recv_audio
    def get_recv_video(self):
        return self.recv_video

    def clear_ports(self):
        self.used_ports = []
        self.send_ip = None
        self.send_audio = None
        self.send_video = None
        self.recv_audio = None
        self.recv_video = None

    def start_rtp_comms(self):
        self.running = True
        threads = []
        if self.send_video:
            threads.append(threading.Thread(target=self._send_audio))
        if self.recv_audio:
            threads.append(threading.Thread(target=self._recv_audio))

    def _send_audio(self):
        # mabye rtpHandler for all audio/all video
        encoder = AudioHandler()
        sender = RTPHandler(self.send_ip, None, self.send_audio)
        ssrc = random.randint(50, 5000)
        sender.start(receive=False)
        while self.running:
            # maybe gui should send data to send?
            payload = encoder.encode()
            packet = RTPPacket(
                ssrc=ssrc
            )
            packet.payload = payload
            sender.send_packet(packet)

            # audio objects -> encode -> send using rtp_handler

            pass

    def _recv_audio(self, decoder):
        receiver = RTPHandler(self.send_ip, self.recv_audio, None)
        receiver.start(receive=True)
        while self.running:
            # start rtp_handler -> add payload to recv queue in manager - use decoder in gui to play
            try:
                frame = receiver.receive_queue.get(timeout=1)
                self.recv_audio_queue.put(frame)
            except Queue.empty:
                continue



