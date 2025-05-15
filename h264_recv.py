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
import av
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
# WIDTH, HEIGHT = 640, 480  # Video resolution
# MAX_PACKET_SIZE = int(1500 / 8)  # Maximum packet size in bytes
#
# def decode_h264_to_frame(h264_data):
#     """
#     Decode H.264 data to a raw frame (BGR format for OpenCV).
#     Returns a NumPy array representing the frame.
#     """
#     try:
#         # Set up ffmpeg process for H.264 decoding
#         process = (
#             ffmpeg
#             .input('pipe:', format='h264')
#             .output('pipe:', format='rawvideo', pix_fmt='bgr24')
#             .run_async(pipe_stdin=True, pipe_stdout=True)
#         )
#
#         # Write H.264 data to ffmpeg stdin
#         process.stdin.write(h264_data)
#         process.stdin.close()
#
#         # Read decoded raw frame data
#         raw_data = process.stdout.read(WIDTH * HEIGHT * 3)  # BGR24: 3 bytes per pixel
#         process.stdout.close()
#         process.wait()
#
#         if not raw_data:
#             return None
#
#         # Convert raw data to NumPy array and reshape to frame
#         frame = np.frombuffer(raw_data, dtype=np.uint8)
#         frame = frame.reshape((HEIGHT, WIDTH, 3))
#         return frame
#
#     except Exception as e:
#         print(f"Error decoding frame: {e}")
#         return None
#
# def main():
#     # Initialize RTPHandler for receiving video
#     rtp_handler = RTPHandler(
#         send_ip=SEND_IP,  # Not used for sending, but required by constructor
#         listen_port=LISTEN_PORT,
#         send_port=SEND_PORT,  # Not used
#         msg_type=PacketType.VIDEO
#     )
#
#     # Start RTPHandler (only receiving, no sending)
#     rtp_handler.start(receive=True, send=False)
#
#     try:
#         while True:
#             try:
#                 # Get RTP packet from receive queue
#                 with rtp_handler.receive_lock:
#                     if not rtp_handler.receive_queue.empty():
#                         rtp_packet = rtp_handler.receive_queue.get(timeout=1.0)
#                         print(rtp_packet)
#                     else:
#                         continue
#
#                 # Ensure it's a video packet
#                 if rtp_packet.payload_type != PacketType.VIDEO.value:
#                     continue
#
#                 # Decode H.264 payload to frame
#                 frame = decode_h264_to_frame(rtp_packet.payload)
#                 if frame is None:
#                     continue
#
#                 # Display the frame
#                 cv2.imshow('Livestream', frame)
#                 if cv2.waitKey(1) & 0xFF == ord('q'):
#                     break
#
#             except queue.Empty:
#                 continue
#             except Exception as e:
#                 print(f"Error processing packet: {e}")
#
#     except KeyboardInterrupt:
#         print("Stopping receiver...")
#     finally:
#         # Cleanup
#         rtp_handler.stop()
#         cv2.destroyAllWindows()
#
# if __name__ == "__main__":
#     main()

import cv2
import numpy as np
from RTP_msgs import RTPPacket, PacketType
from rtp_handler import RTPHandler

def receiver_main():
    decoder = av.codec.CodecContext.create('h264', 'r')
    receiver = RTPHandler(send_ip='127.0.0.1', listen_port=2432, send_port=5006, msg_type=PacketType.VIDEO)
    receiver.start(receive=True, send=False)

    try:
        while True:
            if not receiver.receive_queue.empty():
                pkt = receiver.receive_queue.get()
                img_data = pkt.payload

                packet = av.Packet(img_data)

                frames = decoder.decode(packet)
                for frame in frames:
                    img = frame.to_ndarray(format='bgr24')
                    cv2.imshow('UDP Decoded Video', img)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        cv2.destroyAllWindows()
                        return
    except KeyboardInterrupt:
        print("Receiver stopped.")
    finally:
        receiver.stop()
        cv2.destroyAllWindows()

receiver_main()