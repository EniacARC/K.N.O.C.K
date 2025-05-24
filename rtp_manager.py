import random
import socket
import threading
import time
import queue

import cv2

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
            except Exception:
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
            print(self.recv_audio)
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
        print(str(self))
        if self.send_audio:
            print("send audio")
            self.threads.append(threading.Thread(target=self._send_audio))
        if self.recv_audio:
            self.threads.append(threading.Thread(target=self._recv_audio))
        if self.send_video:
            print("send video")
            self.threads.append(threading.Thread(target=self._send_video))
        if self.recv_video:
            self.threads.append(threading.Thread(target=self._recv_video))

        print(len(self.threads))
        for thread in self.threads:
            thread.start()

    def _send_audio(self):
        # mabye rtpHandler for all audio/all video
        audio_io = AudioInput()
        sender = RTPHandler(self.send_ip, send_port=self.send_audio)
        sender.start()
        while self.running:
            print(f"running loop to send on {self.send_audio}")
            # maybe gui should send data to send?
            audio_data = audio_io.read() # is in bytes
            sender.send_packet(audio_data)
            print(audio_data)

        sender.stop()
        audio_io.close()

            # audio objects -> get_input -> send using rtp_handler

    def _recv_audio(self):
        receiver = RTPHandler(self.send_ip, listen_port=self.recv_audio)
        receiver.start()


        decoder = AudioOutput()
        while self.running:
            # start rtp_handler -> add payload to recv queue in manager -> use AudioOutput to play in gui
            try:
                frame = receiver.receive_queue.get(timeout=1).payload
                # self.recv_audio_queue.put(frame) # no need for decoding
                decoder.write(frame)
            except Exception:
                continue

        receiver.stop()

    def get_next_audio_frame(self):
        return self.recv_audio_queue.get() # blocking

    def _send_video(self):

        # get input -> encode -> send -> sleep(?)
        print(self.send_video)
        video_io = VideoInput()
        encoder = VideoEncoder()
        print("works")

        # hard coding fps for now
        frame_interval = 1.0 / 30.0  # 30 frames per second → 33.3 ms
        sender = RTPHandler(self.send_ip, send_port=self.send_video)
        sender.start()
        print("starting")
        while self.running:
            # print(f"running loop to send on {self.send_video}")
            start_time = time.time()
            video_frame = video_io.get_frame()
            encoded_frame = encoder.encode(video_frame)
            for frame in encoded_frame:
                print(f"sent frame to {self.send_video}")
                sender.send_packet(bytes(frame))

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
                print(f"trying to recv on {self.recv_video}")
                encoded_data = receiver.receive_queue.get(timeout=1).payload
                print(f"got data for port {self.recv_video}: {encoded_data}")
                decoded_frames = decoder.decode(encoded_data)
                print("decoded data")
                for frame in decoded_frames:
                    print("got frame")
                    self.recv_video_queue.put(frame)
                    # img = frame.to_ndarray(format='bgr24')
                    # cv2.imshow('Decoded Frame', img)
                    # if cv2.waitKey(1) & 0xFF == ord('q'):
                    #     return

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

    def __str__(self):
        return (
            f"RTPManager Status:\n"
            f"  Running: {self.running}\n"
            f"  Used Ports: {self.used_ports}\n"
            f"  Send IP: {self.send_ip}\n"
            f"  Send Audio Port: {self.send_audio}\n"
            f"  Send Video Port: {self.send_video}\n"
            f"  Receive Audio Port: {self.recv_audio}\n"
            f"  Receive Video Port: {self.recv_video}\n"
            f"  Audio Queue Size: {self.recv_audio_queue.qsize()}\n"
            f"  Video Queue Size: {self.recv_video_queue.qsize()}\n"
            f"  Threads Running: {len(self.threads)}"
        )


