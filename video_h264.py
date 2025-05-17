import multiprocessing as mp
import random
import socket

import cv2
import av
import time
from fractions import Fraction
import numpy as np

from RTP_msgs import PacketType, RTPPacket
from rtp_handler import RTPHandler

# ----- CONFIG -----
WIDTH, HEIGHT = 640, 480
FPS = 30


def capture_proc(frame_queue: mp.Queue):
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        if not frame_queue.full():
            frame_queue.put(frame)
        # else:
        #     frame_queue.get_nowait()
        #     frame_queue.put(frame)


def encode_proc(frame_queue: mp.Queue):
    sender = RTPHandler(send_ip='127.0.0.1', listen_port=4544, send_port=2432, msg_type=PacketType.VIDEO)
    sender.start(receive=False)

    encoder = av.CodecContext.create('h264', 'w')
    encoder.width = WIDTH
    encoder.height = HEIGHT
    encoder.time_base = Fraction(1, FPS)
    encoder.framerate = Fraction(FPS, 1)
    encoder.pix_fmt = 'yuv420p'
    encoder.options = {
        'preset': 'ultrafast',
        'tune': 'zerolatency',
        'profile': 'baseline',
        'g': '30',
        'bf': '0',
    }
    encoder.max_b_frames = 0
    encoder.open()

    frame_count = 0
    start_time = time.time()
    fps_timer = time.time()
    while True:
        frame = frame_queue.get()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(frame_rgb, format='rgb24')
        video_frame.pts = frame_count
        video_frame.time_base = Fraction(1, FPS)

        packets = encoder.encode(video_frame)
        for pkt in packets:
            frags = RTPHandler.build_packets(0, bytes(pkt))
            for frag in frags:
                sender.send_packet(frag)
                # time.sleep(0.01)
            print("end")

        frame_count += 1

        # === FPS Counter ===
        if time.time() - fps_timer >= 1.0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"[ENCODER] FPS: {fps:.2f}")
            fps_timer = time.time()


if __name__ == '__main__':
    mp.set_start_method('spawn')  # Important for compatibility

    frame_queue = mp.Queue(maxsize=3)

    p1 = mp.Process(target=capture_proc, args=(frame_queue,))
    p2 = mp.Process(target=encode_proc, args=(frame_queue,))

    p1.start()
    p2.start()


    p1.join()
    p2.join()