import threading
from fractions import Fraction
from queue import Queue
from abc import ABC, abstractmethod
import av
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import cv2
import pyaudio

WIDTH, HEIGHT = 640, 480
FPS = 30

# for testing i need to create a singelton for multi threading

class VideoInput:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise Exception("Camera not available!")
        else:
            print("Starting camera")

        # without "os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0" this is really slow
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    def get_frame(self):
        """
        Capture a single video frame from the camera in a thread-safe manner.

        :params: none

        :return: captured video frame as numpy.ndarray or None if failed
        :rtype: numpy.ndarray or None
        """
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None
        return frame

    def close(self):
        """
        Release the camera resource safely with thread synchronization.

        :params: none
        :returns: none
        """
        if self.cap.isOpened():
            self.cap.release()


# singelton for testing
# class VideoInput:
#     _instance = None
#     _instance_lock = threading.Lock()
#
#     def __new__(cls, *args, **kwargs):
#         """
#         Create or return the singleton instance of VideoInput.
#
#         :params: none
#
#         :return: singleton instance of VideoInput
#         :rtype: VideoInput
#         """
#         if not cls._instance:
#             with cls._instance_lock:
#                 if not cls._instance:
#                     cls._instance = super(VideoInput, cls).__new__(cls)
#                     # Initialize internal members here in __new__ or __init__
#         return cls._instance
#
#     def __init__(self):
#         # Avoid reinitializing on subsequent calls
#         if hasattr(self, '_initialized') and self._initialized:
#             return
#
#         self.cap = cv2.VideoCapture(0)
#         if not self.cap.isOpened():
#             print("Camera not available!")
#         else:
#             print("Starting camera")
#
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#         self.cap.set(cv2.CAP_PROP_FPS, FPS)
#         self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
#
#         self._read_lock = threading.Lock()
#         self._initialized = True
#
#     def get_frame(self):
#         """
#         Capture a single video frame from the camera in a thread-safe manner.
#
#         :params: none
#
#         :return: captured video frame as numpy.ndarray or None if failed
#         :rtype: numpy.ndarray or None
#         """
#         with self._read_lock:
#             ret, frame = self.cap.read()
#             if not ret or frame is None:
#                 return None
#             return frame
#
#     def close(self):
#         """
#         Release the camera resource safely with thread synchronization.
#
#         :params: none
#         :returns: none
#         """
#         with self._read_lock:
#             if self.cap.isOpened():
#                 self.cap.release()


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
        """
        Encode a BGR video frame to H.264 format using the PyAV encoder.

        :param frame: input video frame in BGR format (as returned from OpenCV)
        :type frame: numpy.ndarray

        :return: list of encoded video packets
        :rtype: list[av.Packet]
        """
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
        """
        Decode a raw H.264 encoded frame into decoded video frames.

        :param frame: raw H.264 encoded frame bytes
        :type frame: bytes

        :return: list of decoded video frames
        :rtype: list[av.VideoFrame]
        """
        pkt = av.Packet(frame)
        frames = self.decoder.decode(pkt)
        return frames

