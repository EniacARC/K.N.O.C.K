import threading
from fractions import Fraction
from queue import Queue
from abc import ABC, abstractmethod
import av
import cv2
import pyaudio

WIDTH, HEIGHT = 640, 480
FPS = 30

# for testing i need to create a singelton for multi threading
class VideoInput:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    cls._instance = super(VideoInput, cls).__new__(cls)
                    # Initialize internal members here in __new__ or __init__
        return cls._instance

    def __init__(self):
        # Avoid reinitializing on subsequent calls
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Camera not available!")
        else:
            print("Starting camera")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._read_lock = threading.Lock()
        self._initialized = True

    def get_frame(self):
        with self._read_lock:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return None
            return frame

    def close(self):
        with self._read_lock:
            if self.cap.isOpened():
                self.cap.release()

# class VideoInput:
#     def __init__(self):
#         self.cap = cv2.VideoCapture(0)
#         if not self.cap.isOpened():
#             print("Camera not available!")
#         else:
#             print("starting camera")
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#         self.cap.set(cv2.CAP_PROP_FPS, FPS)
#         self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
#
#     def get_frame(self):
#         ret, frame = self.cap.read()
#         if not ret:
#             return None
#         return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#
#     def close(self):
#         self.cap.release()

# class VideoOutput:
#     def display_frame(self, frame):
#         img = frame.to_ndarray(format='bgr24')
#         cv2.imshow('Decoded Frame', img)
#         cv2.waitKey(1)


class VideoEncoder:
    def __init__(self):
        self.encoder = av.CodecContext.create('h264', 'w')
        self.encoder.width = WIDTH
        self.encoder.height = HEIGHT
        self.encoder.time_base = Fraction(1, FPS)
        self.encoder.framerate = Fraction(FPS, 1)
        self.encoder.pix_fmt = 'yuv420p'
        self.encoder.options = {
            'preset': 'ultrafast',
            'tune': 'zerolatency',
            'g': '30',
            'bf': '0'
        }

        self.encoder.max_b_frames = 0
        self.encoder.open()
        # self.read_queue = Queue.queue()

    def encode(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(frame_rgb, format='rgb24')
        packets = self.encoder.encode(video_frame)
        return packets

class VideoDecoder:
    def __init__(self):
        self.decoder = av.CodecContext.create('h264', 'r')
        self.decoder.options = {'flags2': '+fast'}
        self.decoder.open()

    def decode(self, frame):
        pkt = av.Packet(frame)
        frames = self.decoder.decode(pkt)
        return frames

# class VideoHandler:
#     def __init__(self, encoder=True):
#         self.is_encoder = encoder
#         self.cap = cv2.VideoCapture(0)
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#         self.cap.set(cv2.CAP_PROP_FPS, FPS)
#         self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
#         if encoder:
#             self.codec = av.CodecContext.create('h264', 'w')
#             self.codec.width = WIDTH
#             self.codec.height = HEIGHT
#             self.codec.time_base = Fraction(1, FPS)
#             self.codec.framerate = Fraction(FPS, 1)
#             self.codec.pix_fmt = 'yuv420p'
#             self.codec.options = {
#                 'preset': 'ultrafast',
#                 'tune': 'zerolatency',
#                 'g': '30',
#                 'bf': '0'
#             }
#
#             self.codec.max_b_frames = 0
#             # self.read_queue = Queue.queue()
#         else:
#             self.codec = av.CodecContext.create('h264', 'r')
#             self.codec.options = {'flags2': '+fast'}
#         self.codec.open()
#
#     def encode(self):
#         if self.is_encoder:
#             ret, frame = self.cap.read()
#             if not ret:
#                 return None
#             frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             video_frame = av.VideoFrame.from_ndarray(frame_rgb, format='rgb24')
#             video_frame.time_base = Fraction(1, FPS)
#
#             return self.codec.encode(video_frame)
#         else:
#             raise RuntimeError("cannot encode in decode mode")
#
#     def decoder(self, video_frame):
#         try:
#             frames = self.codec.decode(video_frame)
#             for frame in frames:
#                 yield frame
#         except Exception:
#             return None
#         else:
#             raise RuntimeError("cannot decode in encode mode")
#
#     def close(self):
#         self.stream.close()
#         self.audio.terminate()
