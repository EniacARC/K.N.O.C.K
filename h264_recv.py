import time
from tkinter.font import names

import av
import cv2

from RTP_msgs import PacketType
from rtp_handler import *


def decode_proc():
    receiver = RTPHandler(send_ip='127.0.0.1', listen_port=2432, send_port=5006, msg_type=PacketType.VIDEO)
    receiver.start(receive=True)
    decoder = av.CodecContext.create('h264', 'r')
    decoder.options = {'flags2': '+fast'}
    decoder.open()

    frame_count = 0
    start_time = time.time()

    while True:
        try:
            with receiver.receive_lock:
                if not receiver.receive_queue.empty():
                    frm = receiver.receive_queue.get()
                else:
                    time.sleep(0.01)
            pkt = av.Packet(frm.payload)
            frm = None

            frames = decoder.decode(pkt)
            for f in frames:
                img = f.to_ndarray(format='bgr24')
                cv2.imshow('Decoded Frame', img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    return
        except Exception:
            continue

        frame_count += 1
        elapsed = time.time() - start_time
        if elapsed > 1.0:
            fps_actual = frame_count / elapsed
            print(f'Decoded FPS: {fps_actual:.2f}')
            frame_count = 0
            start_time = time.time()

if __name__ == '__main__':
    decode_proc()