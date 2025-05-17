# import threading
# import queue
# import time
# import av
# import cv2
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
#
# WIDTH, HEIGHT = 640, 480
#
# class DecoderThread(threading.Thread):
#     def __init__(self, packet_queue, frame_queue):
#         super().__init__()
#         self.packet_queue = packet_queue
#         self.frame_queue = frame_queue
#         self.running = True
#         self.decoder = av.codec.CodecContext.create('h264', 'r')
#         self.decoder.options = {
#             'fflags': 'nobuffer',
#             'flags2': '+fast',
#             'low_delay': '1',
#         }
#         self.decoder.pix_fmt = 'yuv420p'
#
#         # FPS measurement variables
#         self.frame_count = 0
#         self.last_time = time.time()
#
#     def run(self):
#         while self.running:
#             try:
#                 pkt = self.packet_queue.get(timeout=0.5)
#             except queue.Empty:
#                 continue
#
#             try:
#                 av_packet = av.Packet(pkt.payload)
#                 frames = self.decoder.decode(av_packet)
#                 for frame in frames:
#                     img = frame.to_ndarray(format='bgr24')
#                     try:
#                         self.frame_queue.put_nowait(img)
#                     except queue.Full:
#                         pass
#
#                     # Count frames and print FPS once per second
#                     self.frame_count += 1
#                     now = time.time()
#                     if now - self.last_time >= 1.0:
#                         print(f"[Decoder FPS] {self.frame_count}")
#                         self.frame_count = 0
#                         self.last_time = now
#
#             except Exception as e:
#                 print(f"[Decode Error] {e}")
#
#     def stop(self):
#         self.running = False
#         self.join(timeout=1.0)
#         self.decoder.close()
#
# class DisplayThread(threading.Thread):
#     def __init__(self, frame_queue):
#         super().__init__()
#         self.frame_queue = frame_queue
#         self.running = True
#
#         # FPS measurement variables
#         self.frame_count = 0
#         self.last_time = time.time()
#
#     def run(self):
#         while self.running:
#             try:
#                 frame = self.frame_queue.get(timeout=0.5)
#             except queue.Empty:
#                 continue
#
#             cv2.imshow('UDP Decoded Video', frame)
#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 self.running = False
#
#             self.frame_count += 1
#             now = time.time()
#             if now - self.last_time >= 1.0:
#                 print(f"[Display FPS] {self.frame_count}")
#                 self.frame_count = 0
#                 self.last_time = now
#
#     def stop(self):
#         self.running = False
#         self.join(timeout=1.0)
#         cv2.destroyAllWindows()
#
# def main():
#     packet_queue = queue.Queue(maxsize=100)
#     frame_queue = queue.Queue(maxsize=30)
#
#     receiver = RTPHandler(send_ip='127.0.0.1', listen_port=2432, send_port=5006, msg_type=PacketType.VIDEO)
#     receiver.start(receive=True, send=False)
#
#     decoder_thread = DecoderThread(packet_queue, frame_queue)
#     display_thread = DisplayThread(frame_queue)
#
#     decoder_thread.start()
#     display_thread.start()
#
#     try:
#         while display_thread.running:
#             if not receiver.receive_queue.empty():
#                 with receiver.receive_lock:
#                     pkt = receiver.receive_queue.get()
#                 if pkt.payload_type != PacketType.VIDEO.value:
#                     continue
#                 try:
#                     packet_queue.put_nowait(pkt)
#                 except queue.Full:
#                     pass
#
#     except KeyboardInterrupt:
#         print("Stopping...")
#
#     finally:
#         decoder_thread.stop()
#         display_thread.stop()
#         receiver.stop()
#
# if __name__ == "__main__":
#     main()
# import threading
# import queue
# import time
# import av
# import cv2
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
#
# WIDTH, HEIGHT = 640, 480
# FPS = 30
#
# class DecoderThread(threading.Thread):
#     def __init__(self, packet_queue):
#         super().__init__()
#         self.packet_queue = packet_queue
#         self.running = True
#         self.decoder = av.codec.CodecContext.create('h264', 'r')
#         self.decoder.options = {
#             'tune': 'zerolatency',
#             'preset': 'ultrafast',
#             'threads': 'auto',
#             'fast': '1',
#             'skip_loop_filter': 'all',
#             'flags2': 'fast',
#             'max_delay': '0',
#         }
#         self.decoder.pix_fmt = 'yuv420p'
#
#         # FPS measurement
#         self.frame_count = 0
#         self.fps_start_time = time.time()
#
#     def run(self):
#         while self.running:
#             try:
#                 pkt = self.packet_queue.get(timeout=0.5)
#             except queue.Empty:
#                 continue
#
#             try:
#                 av_packet = av.Packet(pkt.payload)
#                 frames = self.decoder.decode(av_packet)
#                 for frame in frames:
#                     img = frame.to_ndarray(format='bgr24')
#                     cv2.imshow('UDP Decoded Video', img)
#                     if cv2.waitKey(1) & 0xFF == ord('q'):
#                         self.running = False
#                         return
#
#                     # Count frames for FPS
#                     self.frame_count += 1
#                     elapsed = time.time() - self.fps_start_time
#                     if elapsed >= 1.0:
#                         print(f"Decoding FPS: {self.frame_count / elapsed:.2f}")
#                         self.frame_count = 0
#                         self.fps_start_time = time.time()
#             except Exception as e:
#                 print(f"[Decode Error] {e}")
#
#     def stop(self):
#         self.running = False
#         self.join(timeout=1.0)
#         self.decoder.close()
#
# def main():
#     packet_queue = queue.Queue(maxsize=100)
#
#     receiver = RTPHandler(send_ip='127.0.0.1', listen_port=2432, send_port=5006, msg_type=PacketType.VIDEO)
#     receiver.start(receive=True, send=False)
#
#     decoder_thread = DecoderThread(packet_queue)
#     decoder_thread.start()
#
#     try:
#         while True:
#             if not receiver.receive_queue.empty():
#                 with receiver.receive_lock:
#                     pkt = receiver.receive_queue.get()
#                 if pkt.payload_type != PacketType.VIDEO.value:
#                     continue
#                 try:
#                     packet_queue.put_nowait(pkt)
#                 except queue.Full:
#                     # Drop packet if queue full
#                     pass
#             else:
#                 time.sleep(0.01)
#     except KeyboardInterrupt:
#         print("Stopping receiver...")
#     finally:
#         decoder_thread.stop()
#         receiver.stop()
#         cv2.destroyAllWindows()
#
# if __name__ == "__main__":
#     main()
import socket
import time
# import av
# import cv2
# import numpy as np
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
#
# # Configuration (must match sender)
# SEND_IP = "127.0.0.1"
# LISTEN_PORT = 2432
# SEND_PORT = 5006
# FRAME_RATE = 30
# WIDTH, HEIGHT = 640, 480
#
# def create_av_decoder():
#     """Create an AV decoder for H.264."""
#     try:
#         codec = av.Codec('h264', 'r')
#         codec_context = codec.create()
#         codec_context.width = WIDTH
#         codec_context.height = HEIGHT
#         codec_context.pix_fmt = 'yuv420p'
#         codec_context.thread_count = 4
#         print("Decoder initialized successfully")
#         return codec_context
#     except Exception as e:
#         print(f"Error initializing decoder: {e}")
#         return None
#
# def reassemble_nal_unit(packets):
#     """Reassemble fragmented NAL units from RTP payloads."""
#     if not packets:
#         return None
#
#     nal_unit = bytearray()
#     for payload in packets:
#         if len(payload) < 2:
#             continue
#
#         if payload[0] & 0x1F != 28:  # Single NAL unit
#             nal_unit.extend(payload)
#         else:  # FU-A packet
#             fu_indicator = payload[0]
#             fu_header = payload[1]
#             nal_type = fu_header & 0x1F
#             is_start = fu_header & 0x80
#             is_end = fu_header & 0x40
#
#             if is_start:
#                 nal_unit = bytearray([0, 0, 0, 1])
#                 nal_unit.append((fu_indicator & 0xE0) | nal_type)
#             nal_unit.extend(payload[2:])
#
#     return bytes(nal_unit) if nal_unit else None
#
# def main():
#     # Initialize RTPHandler
#     rtp_handler = RTPHandler(
#         send_ip=SEND_IP,
#         listen_port=LISTEN_PORT,
#         send_port=SEND_PORT,
#         msg_type=PacketType.VIDEO
#     )
#     rtp_handler.start(receive=True, send=False)
#
#     codec_context = None
#     packet_buffer = {}
#     last_seq_num = {}
#
#     try:
#         while True:
#             try:
#                 with rtp_handler.receive_lock:
#                     if rtp_handler.receive_queue.empty():
#                         continue
#                     rtp_packet = rtp_handler.receive_queue.get(timeout=1.0)
#                     print(f"Received RTP packet: seq={rtp_packet.seq_num}, marker={rtp_packet.marker}, payload_len={len(rtp_packet.payload)}")
#
#                 if rtp_packet.payload_type != PacketType.VIDEO.value:
#                     continue
#
#                 ssrc = rtp_packet.ssrc
#                 seq_num = rtp_packet.seq_num
#
#                 if ssrc not in packet_buffer:
#                     packet_buffer[ssrc] = []
#                     last_seq_num[ssrc] = seq_num - 1
#
#                 expected_seq = (last_seq_num[ssrc] + 1) % 65536
#                 if seq_num != expected_seq:
#                     print(f"Packet loss or reordering: expected {expected_seq}, got {seq_num}")
#                     packet_buffer[ssrc] = []
#
#                 last_seq_num[ssrc] = seq_num
#                 packet_buffer[ssrc].append(rtp_packet.payload)
#
#                 if rtp_packet.marker:
#                     nal_unit = reassemble_nal_unit(packet_buffer[ssrc])
#                     packet_buffer[ssrc] = []
#
#                     if nal_unit:
#                         if codec_context is None:
#                             codec_context = create_av_decoder()
#                             if codec_context is None:
#                                 print("Failed to initialize decoder, skipping frame")
#                                 continue
#
#                         try:
#                             # Parse raw H.264 NAL unit into packets
#                             packets = codec_context.parse(nal_unit)
#                             for packet in packets:
#                                 # Decode parsed packets into frames
#                                 frames = codec_context.decode(packet)
#                                 for frame in frames:
#                                     if frame:
#                                         frame_rgb = frame.to_ndarray(format='rgb24')
#                                         frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
#                                         cv2.imshow('Received Stream', frame_bgr)
#                                         print(f"Displayed decoded frame: {frame.width}x{frame.height}")
#                         except Exception as e:
#                             print(f"Error decoding packet: {e}")
#                             codec_context = None  # Reset decoder on error
#
#                 if cv2.waitKey(1) & 0xFF == ord('q'):
#                     break
#
#             except Exception as e:
#                 print(f"Error processing packet: {e}")
#                 continue
#
#     except KeyboardInterrupt:
#         print("Stopping receiver...")
#     finally:
#         rtp_handler.stop()
#         if codec_context:
#             codec_context.close()
#         cv2.destroyAllWindows()
#
# if __name__ == "__main__":
#     main()
#
# # import asyncio
# # import av
# # import cv2
# # import io
# # from multiprocessing import Process, Queue, Event
# # import time
# # from rtp_handler import *
# #
# # SEND_IP = "127.0.0.1"
# # LISTEN_PORT = 2432
# # SEND_PORT = 5006
# # FRAME_RATE = 30
# # WIDTH, HEIGHT = 640, 480
# #
# #
# # def display_frame(frame, start_time, pts_offset, frame_rate):
# #     if frame.pts is not None:
# #         play_time = (frame.pts - pts_offset) * frame.time_base.numerator / frame.time_base.denominator
# #         if start_time is not None:
# #             current_time = time.time() - start_time
# #             time_diff = play_time - current_time
# #             if time_diff > 1 / frame_rate:
# #                 return False
# #             if time_diff > 0:
# #                 time.sleep(time_diff)
# #     img = frame.to_ndarray(format='bgr24')
# #     cv2.imshow('Video', img)
# #     return True
# #
# # def get_pts(frame):
# #     return frame.pts
# #
# # def render(terminated, data_queue):
# #     codec = av.CodecContext.create("h264", "r")
# #     frames_buffer = []
# #     start_time = None
# #     pts_offset = None
# #     got_key_frame = False
# #
# #     while not terminated.is_set():
# #         try:
# #             data = data_queue.get_nowait()
# #         except:
# #             time.sleep(0.01)
# #             continue
# #
# #         packet = av.Packet(data)
# #
# #         # Optional: wait for a keyframe before decoding to avoid artifacts
# #         if not got_key_frame and packet.is_keyframe:
# #             got_key_frame = True
# #
# #         if data_queue.qsize() > 8 and not packet.is_keyframe:
# #             got_key_frame = False
# #             continue
# #
# #         if not got_key_frame:
# #             continue
# #
# #         frames = codec.decode(packet)
# #
# #         if start_time is None:
# #             start_time = time.time()
# #
# #         for frame in frames:
# #             if pts_offset is None:
# #                 pts_offset = frame.pts
# #
# #             if display_frame(frame, start_time, pts_offset, FRAME_RATE):
# #                 continue
# #
# #             if cv2.waitKey(1) & 0xFF == ord('q'):
# #                 terminated.set()
# #                 break
# #
# #     cv2.destroyAllWindows()
# #
# # async def receive_encoded_video():
# #
# #     rtp_handler = RTPHandler(
# #         send_ip=SEND_IP,
# #         listen_port=LISTEN_PORT,
# #         send_port=SEND_PORT,
# #         msg_type=PacketType.VIDEO
# #     )
# #     rtp_handler.start(receive=True, send=False)
# #     data_queue = Queue()
# #     terminated = Event()
# #     p = Process(
# #         target=render,
# #         args=(terminated, data_queue)
# #     )
# #     p.start()
# #     while not terminated.is_set():
# #         try:
# #             with rtp_handler.receive_lock:
# #                 if not rtp_handler.receive_queue.empty():
# #                     rtp_packet = rtp_handler.receive_queue.get(timeout=1.0)
# #                     data_queue.put(rtp_packet.payload)
# #                 else:
# #                     continue
# #         except:
# #             break
# #     # terminated.set()
# # if __name__ == "__main__":
# #     try:
# #         asyncio.run(receive_encoded_video())
# #     except KeyboardInterrupt:
# #         print("Interrupted by user.")
from fractions import Fraction

import av
import cv2

from RTP_msgs import PacketType, RTPPacket
from rtp_handler import RTPHandler


# import cv2
# import queue
# import ffmpeg
# import numpy as np
# import threading
# from RTP_msgs import RTPPacket, PacketType  # Ensure this is correctly implemented
# from rtp_handler import *  # Use the RTPHandler from your provided code
#
# # Configuration (must match sender)
# SEND_IP = "127.0.0.1"  # Destination IP (sender's IP)
# LISTEN_PORT = 5004  # Port to bind for receiving
# SEND_PORT = 5004  # Port to send RTP packets to (not used in receiver)
# FRAME_RATE = 30  # Target frame rate

def decode_proc():
    # receiver = RTPHandler(send_ip='127.0.0.1', listen_port=2432, send_port=5006, msg_type=PacketType.VIDEO)
    # receiver.start(receive=True, send=False)
    decoder = av.CodecContext.create('h264', 'r')
    decoder.options = {'flags2': '+fast'}
    decoder.open()

    frame_count = 0
    start_time = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 2432))
    sock.settimeout(0.5)
    recv_payload = None
    frm = None

    while True:
        try:
            data, addr = sock.recvfrom(1500)  # Max UDP packet size
        except socket.timeout:
            continue

        packet = RTPPacket()
        if packet.decode_packet(data):
            #     print(packet)
            if recv_payload and recv_payload.timestamp != packet.timestamp:
                print("dropped")
                # Timestamp mismatch: discard previous fragment
                recv_payload = None
            if packet.marker:
                if recv_payload:
                    # if it's not none then timestamps must match
                    recv_payload.payload += packet.payload
                    frm = recv_payload
                    recv_payload = None
                else:
                    # No ongoing fragment or mismatch, queue this as a full packet
                    frm = recv_payload
            else:
                # Intermediate fragment
                if recv_payload:
                    # if it's not none then timestamps must match
                    # Continue building the current payload
                    recv_payload.payload += packet.payload
                else:
                    # Start a new fragmented payload
                    recv_payload = packet

        try:
            if frm is None:
                continue
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

decode_proc()