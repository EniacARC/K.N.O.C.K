import random
import socket
import threading
import time
import queue

from mediator_connect import *
from rtp_handler import RTPHandler
from audio_capture import AudioInput, AudioOutput
from video_capture import VideoInput, VideoEncoder, VideoDecoder
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
        self.threads = []

        self.recv_audio_queue = queue.Queue() # (timestamp, frame)
        self.recv_video_queue = queue.Queue() # (timestamp, frame)
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
        self.threads = []
        self.running = False
        self.send_ip = None
        self.send_audio = None
        self.send_video = None
        self.recv_audio = None
        self.recv_video = None

    def start_rtp_comms(self):
        self.running = True
        if self.send_audio:
            self.threads.append(threading.Thread(target=self._send_audio))
        if self.recv_audio:
            self.threads.append(threading.Thread(target=self._recv_audio))

        if self.send_video:
            self.threads.append(threading.Thread(target=self._send_video))
        if self.recv_video:
            self.threads.append(threading.Thread(target=self._recv_video))

        for thread in self.threads:
            thread.start()

    def _send_audio(self):
        # mabye rtpHandler for all audio/all video
        audio_io = AudioInput()
        sender = RTPHandler(self.send_ip, send_port=self.send_audio)
        sender.start()
        while self.running:
            # maybe gui should send data to send?
            audio_data = audio_io.read()
            sender.send_packet(audio_data)

        sender.stop()

            # audio objects -> get_input -> send using rtp_handler

    def _recv_audio(self, decoder):
        receiver = RTPHandler(self.send_ip, listen_port=self.recv_audio)
        receiver.start()
        while self.running:
            # start rtp_handler -> add payload to recv queue in manager -> use AudioOutput to play in gui
            try:
                frame = receiver.receive_queue.get(timeout=1).payload
                self.recv_audio_queue.put(frame) # no need for decoding
            except Exception:
                continue

        receiver.stop()

    def get_next_audio_frame(self):
        return self.recv_audio_queue.get() # blocking

    def _send_video(self):

        # get input -> encode -> send -> sleep(?)

        video_io = VideoInput()
        encoder = VideoEncoder()

        # hard coding fps for now
        frame_interval = 1.0 / 30.0  # 30 frames per second → 33.3 ms

        sender = RTPHandler(self.send_ip, send_port=self.send_audio)
        sender.start()
        while self.running:
            start_time = time.time()
            video_frame = video_io.get_frame()
            encoded_frame = encoder.encode(video_frame)
            for frame in encoded_frame:
                sender.send_packet(frame)

            # SEND MAX 30 FPS
            elapsed = time.time() - start_time
            sleep_time = max(0.0, frame_interval - elapsed)
            time.sleep(sleep_time)

        sender.stop()
    def _recv_video(self):
        # start rtp_handler -> decode_packet -> play frame in gui
        receiver = RTPHandler(self.send_ip, listen_port=self.recv_video)
        decoder = VideoDecoder()
        receiver.start()
        while self.running:
            # start rtp_handler -> add payload to recv queue in manager -> use AudioOutput to play in gui
            try:
                encoded_data = receiver.receive_queue.get(timeout=1).payload
                decoded_frames = decoder.decode(encoded_data)
                for frame in decoded_frames:
                    self.recv_video_queue.put(frame)

            except Exception:
                continue

        receiver.stop()
    def get_next_video_frame(self):
        return self.recv_video_queue.get()  # blocking

    def stop(self):
        self.running = False
        for thread in self.threads:
            thread.join()
        self.clear_ports()



