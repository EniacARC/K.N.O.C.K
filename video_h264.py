# import av
# import cv2
# import numpy as np
# import time
# import random
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
#
# # Configuration
# SEND_IP = "127.0.0.1"
# LISTEN_PORT = 5006
# SEND_PORT = 2432
# FRAME_RATE = 30
# WIDTH, HEIGHT = 640, 480
# MAX_PACKET_SIZE = 1400  # Bytes, respecting MTU
#
# def create_av_encoder():
#     """Create an AV encoder for H.264."""
#     container = av.open('pipe:', format='rawvideo', mode='w')
#     stream = container.add_stream('libx264', rate=FRAME_RATE)
#     stream.width = WIDTH
#     stream.height = HEIGHT
#     stream.pix_fmt = 'yuv420p'
#     stream.options = {
#         'preset': 'ultrafast',
#         'tune': 'zerolatency',
#         'crf': '23',
#         'threads': '4'
#     }
#     return container, stream
#
# def fragment_nal_units(h264_data, max_packet_size):
#     """Fragment H.264 NAL units into RTP payloads."""
#     packets = []
#     start = 0
#     while start < len(h264_data):
#         # Look for NAL unit start codes (0x000001 or 0x00000001)
#         if start + 3 >= len(h264_data):
#             break
#         if h264_data[start:start+3] == b'\x00\x00\x01':
#             nal_start = start
#             start += 3
#         elif start + 4 < len(h264_data) and h264_data[start:start+4] == b'\x00\x00\x00\x01':
#             nal_start = start
#             start += 4
#         else:
#             start += 1
#             continue
#
#         # Find next NAL unit
#         next_nal = len(h264_data)
#         for i in range(start, len(h264_data) - 3):
#             if h264_data[i:i+3] == b'\x00\x00\x01':
#                 next_nal = i
#                 break
#             if i + 1 < len(h264_data) - 3 and h264_data[i:i+4] == b'\x00\x00\x00\x01':
#                 next_nal = i
#                 break
#
#         nal_unit = h264_data[nal_start:next_nal]
#         nal_size = len(nal_unit)
#
#         if nal_size <= max_packet_size - 2:
#             # Single NAL unit packet
#             packets.append(nal_unit)
#         else:
#             # Fragmentation Unit (FU-A)
#             nal_type = nal_unit[nal_start+3 if nal_start+3 < len(nal_unit) else 0] & 0x1F
#             fu_payload = nal_unit[nal_start+4 if nal_start+4 < len(nal_unit) else nal_start+3:]
#             offset = 0
#             while offset < len(fu_payload):
#                 chunk_size = min(max_packet_size - 3, len(fu_payload) - offset)
#                 fu_indicator = (0x1C << 3) | (nal_type & 0x1F)  # FU-A
#                 fu_header = 0
#                 if offset == 0:
#                     fu_header |= 0x80  # Start bit
#                 if offset + chunk_size >= len(fu_payload):
#                     fu_header |= 0x40  # End bit
#                 fu_header |= (nal_type & 0x1F)
#                 packet = bytearray([fu_indicator, fu_header]) + fu_payload[offset:offset+chunk_size]
#                 packets.append(bytes(packet))
#                 offset += chunk_size
#
#         start = next_nal
#
#     return packets
#
# def main():
#     # Initialize webcam
#     cap = cv2.VideoCapture(0)
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#     cap.set(cv2.CAP_PROP_FPS, FRAME_RATE)
#
#     if not cap.isOpened():
#         print("Error: Could not open webcam")
#         return
#
#     # Initialize encoder
#     container, stream = create_av_encoder()
#
#     # Initialize RTPHandler
#     rtp_handler = RTPHandler(
#         send_ip=SEND_IP,
#         listen_port=LISTEN_PORT,
#         send_port=SEND_PORT,
#         msg_type=PacketType.VIDEO
#     )
#     rtp_handler.start(receive=False, send=True)
#
#     # RTP parameters
#     clock_rate = 90000  # 90 kHz for video
#     start_time = time.time()
#     seq_num = 0
#     ssrc = random.randint(0, 4294967295)
#
#     # FPS tracking
#     fps_frame_count = 0
#     fps_start_time = time.time()
#
#     try:
#         while True:
#             ret, frame = cap.read()
#             if not ret:
#                 print("Error: Failed to capture frame")
#                 continue
#
#             # Convert BGR to RGB
#             frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#
#             # Create AV frame
#             av_frame = av.VideoFrame.from_ndarray(frame_rgb, format='rgb24')
#             av_frame.pts = int((time.time() - start_time) * FRAME_RATE)
#
#             # Encode frame
#             packets = []
#             for packet in stream.encode(av_frame):
#                 if packet.size > 0:
#                     packets.extend(fragment_nal_units(bytes(packet), MAX_PACKET_SIZE))
#
#             # Send RTP packets
#             timestamp = int((time.time() - start_time) * clock_rate)
#             for i, payload in enumerate(packets):
#                 rtp_packet = RTPPacket()
#                 rtp_packet.payload = payload
#                 rtp_packet.timestamp = timestamp
#                 rtp_packet.seq_num = seq_num
#                 rtp_packet.marker = (i == len(packets) - 1)  # Marker on last packet
#                 rtp_packet.ssrc = ssrc
#                 rtp_packet.payload_type = PacketType.VIDEO.value
#
#                 try:
#                     with rtp_handler.send_lock:
#                         rtp_handler.send_queue.put_nowait(rtp_packet)
#                 except:
#                     pass  # Drop packet if queue is full
#
#                 seq_num = (seq_num + 1) % 65536
#
#             # FPS calculation
#             fps_frame_count += 1
#             current_time = time.time()
#             if current_time - fps_start_time >= 1.0:
#                 fps = fps_frame_count / (current_time - fps_start_time)
#                 print(f"Encoding FPS: {fps:.2f}")
#                 fps_frame_count = 0
#                 fps_start_time = current_time
#
#             time.sleep(1 / FRAME_RATE)  # Control frame rate
#
#     except KeyboardInterrupt:
#         print("Stopping sender...")
#     finally:
#         cap.release()
#         container.close()
#         rtp_handler.stop()
#
# if __name__ == "__main__":
#     main()
from fractions import Fraction

import av
# import queue
# import random
# import cv2
# import numpy as np
# import time
# import subprocess
# import os
# from RTP_msgs import *  # Ensure this is correctly implemented
# from rtp_handler import *
#
# # Configuration
# SEND_IP = "127.0.0.1"  # Destination IP (e.g., receiver's IP)
# LISTEN_PORT = 4324  # Port to bind for receiving (if needed)
# SEND_PORT = 5004  # Port to send RTP packets to
# FRAME_RATE = 30  # Target frame rate
# WIDTH, HEIGHT = 640, 480  # Video resolution
#
#
# # Create a persistent ffmpeg process for encoding
# def create_ffmpeg_encoder():
#     """Create a persistent FFmpeg process for H.264 encoding"""
#     # Create FFmpeg command for H.264 encoding
#     cmd = [
#         'ffmpeg',
#         '-f', 'rawvideo',  # Input format: raw video
#         '-pix_fmt', 'rgb24',  # Pixel format: RGB24
#         '-s', f'{WIDTH}x{HEIGHT}',  # Frame size
#         '-r', str(FRAME_RATE),  # Frame rate
#         '-i', 'pipe:',  # Input from pipe
#         '-an',  # No audio
#         '-c:v', 'libx264',  # Video codec: H.264
#         '-preset', 'ultrafast',  # Encoding preset
#         '-tune', 'zerolatency',  # Optimize for low latency
#         '-threads', '4',  # Use multiple threads
#         '-f', 'h264',  # Output format: H.264
#         'pipe:'  # Output to pipe
#     ]
#
#     # Create FFmpeg process
#     process = subprocess.Popen(
#         cmd,
#         stdin=subprocess.PIPE,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         bufsize=10 ** 8
#     )
#
#     return process
#
#
# class FrameEncoder:
#     def __init__(self):
#         self.encoder_process = create_ffmpeg_encoder()
#         self.encoded_queue = queue.Queue(maxsize=30)
#         self.running = False
#         self.encoder_thread = None
#
#     def start(self):
#         """Start the encoder thread"""
#         self.running = True
#         self.encoder_thread = threading.Thread(target=self._encoder_read_loop)
#         self.encoder_thread.daemon = True
#         self.encoder_thread.start()
#
#     def stop(self):
#         """Stop the encoder thread and clean up"""
#         self.running = False
#         if self.encoder_thread:
#             self.encoder_thread.join(timeout=1.0)
#
#         if self.encoder_process:
#             try:
#                 self.encoder_process.stdin.close()
#                 self.encoder_process.stdout.close()
#                 self.encoder_process.terminate()
#                 self.encoder_process.wait(timeout=1.0)
#             except:
#                 pass
#
#     def encode_frame(self, frame):
#         """Submit a frame for encoding"""
#         try:
#             if self.encoder_process and self.encoder_process.poll() is None:
#                 # Convert frame from BGR to RGB if using OpenCV
#                 if frame.shape[2] == 3:  # Check if it's a color frame
#                     frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#
#                 # Write frame to FFmpeg's stdin
#                 self.encoder_process.stdin.write(frame.tobytes())
#                 self.encoder_process.stdin.flush()
#                 return True
#             else:
#                 # Restart encoder if it crashed
#                 print("Restarting encoder process...")
#                 self.encoder_process = create_ffmpeg_encoder()
#                 return False
#         except Exception as e:
#             print(f"Error encoding frame: {e}")
#             return False
#
#     def _encoder_read_loop(self):
#         """Background thread that reads encoded data from FFmpeg"""
#         buffer = bytearray()
#
#         while self.running:
#             try:
#                 # Read data from FFmpeg's stdout
#                 chunk = self.encoder_process.stdout.read(4096)
#                 if not chunk:
#                     time.sleep(0.001)  # Small sleep to prevent CPU spin
#                     continue
#
#                 buffer.extend(chunk)
#
#                 # Look for NAL unit boundaries (typically starts with 0x00 0x00 0x00 0x01 or 0x00 0x00 0x01)
#                 # For simplicity, we'll treat each chunk as a complete unit
#                 if len(buffer) > 0:
#                     # Put encoded data in queue, drop if queue is full
#                     try:
#                         self.encoded_queue.put_nowait(bytes(buffer))
#                         buffer.clear()
#                     except queue.Full:
#                         # Drop oldest encoded data to make room
#                         try:
#                             self.encoded_queue.get_nowait()
#                             self.encoded_queue.put_nowait(bytes(buffer))
#                             buffer.clear()
#                         except:
#                             pass
#             except Exception as e:
#                 print(f"Error in encoder read loop: {e}")
#                 time.sleep(0.01)  # Brief pause to prevent CPU spinning on error
#
#     def get_encoded_data(self, timeout=0.1):
#         """Get encoded H.264 data from the queue"""
#         try:
#             return self.encoded_queue.get(timeout=timeout)
#         except queue.Empty:
#             return None
#
#
# def main():
#     # Initialize webcam
#     cap = cv2.VideoCapture(0)
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#     cap.set(cv2.CAP_PROP_FPS, FRAME_RATE)
#
#     if not cap.isOpened():
#         print("Error: Could not open webcam")
#         return
#
#     # Initialize frame encoder
#     encoder = FrameEncoder()
#     encoder.start()
#
#     # Initialize RTPHandler for sending video
#     rtp_handler = RTPHandler(
#         send_ip=SEND_IP,
#         listen_port=LISTEN_PORT,
#         send_port=SEND_PORT,
#         msg_type=PacketType.VIDEO
#     )
#
#     # Start RTPHandler (only sending, no receiving)
#     rtp_handler.start(receive=False, send=True)
#
#     # Clock for RTP timestamps (90 kHz for video)
#     clock_rate = 90000
#     start_time = time.time()
#     frame_count = 0
#     seq_num = 0
#
#     # For measuring FPS
#     fps_frame_count = 0
#     fps_start_time = time.time()
#
#     try:
#         while True:
#             # Capture frame
#             ret, frame = cap.read()
#             if not ret:
#                 print("Error: Failed to capture frame")
#                 break
#
#             # Submit frame for encoding
#             encoder.encode_frame(frame)
#
#             # Check for encoded data
#             h264_data = encoder.get_encoded_data()
#             if h264_data:
#                 # Create RTP packet
#                 timestamp = int((time.time() - start_time) * clock_rate)
#                 rtp_packet = RTPPacket()
#                 rtp_packet.payload = h264_data
#                 rtp_packet.timestamp = timestamp
#                 rtp_packet.seq_num = seq_num
#                 seq_num = (seq_num + 1) % 65536  # Wrap around at 16 bits
#                 rtp_packet.marker = True  # Set marker for the last packet of the frame
#                 rtp_packet.ssrc = random.randint(0, 4294967295)  # Random SSRC
#
#                 # Add packet to send queue without blocking
#                 try:
#                     with rtp_handler.send_lock:
#                         rtp_handler.send_queue.put_nowait(rtp_packet)
#                 # except queue.Full:
#                 #     # If queue is full, remove oldest packet and add new one
#                 #     try:
#                 #         rtp_handler.send_queue.get_nowait()
#                 #         rtp_handler.send_queue.put_nowait(rtp_packet)
#                 except queue.Full:
#                     pass
#
#                 # Count frames for FPS calculation
#                 fps_frame_count += 1
#                 current_time = time.time()
#                 if current_time - fps_start_time >= 1.0:
#                     fps = fps_frame_count / (current_time - fps_start_time)
#                     print(f"Encoding FPS: {fps:.2f}")
#                     fps_frame_count = 0
#                     fps_start_time = current_time
#
#             frame_count += 1
#
#             # Optional: For debugging, display the frame being sent
#             # cv2.imshow('Sending', frame)
#             # if cv2.waitKey(1) & 0xFF == ord('q'):
#             #     break
#
#     except KeyboardInterrupt:
#         print("Stopping stream...")
#     finally:
#         # Cleanup
#         cap.release()
#         encoder.stop()
#         rtp_handler.stop()
#         cv2.destroyAllWindows()
#
#
# if __name__ == "__main__":
#     main()

import cv2
import time
from RTP_msgs import RTPPacket, PacketType
from rtp_handler import *

def sender_main():
    cap = cv2.VideoCapture(0)  # Open default webcam
    sender = RTPHandler(send_ip='127.0.0.1', listen_port=5006, send_port=2432, msg_type=PacketType.VIDEO)
    sender.start(receive=False, send=True)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue

            # Create RTP packet
            pkt = RTPPacket(
                payload_type=PacketType.VIDEO.value,
                marker=True,
            )
            pkt.payload = buffer.tobytes()

            with sender.send_lock:
                sender.send_queue.put(pkt)

            time.sleep(1/30)  # ~30 FPS
    except KeyboardInterrupt:
        print("Sender stopped.")
    finally:
        cap.release()
        sender.stop()


def main():
    # Open webcam with OpenCV
    cap = cv2.VideoCapture(0)  # Change index if needed
    sender = RTPHandler(send_ip='127.0.0.1', listen_port=5006, send_port=2432, msg_type=PacketType.VIDEO)
    sender.start(receive=False, send=True)

    # Encoder setup (H.264)
    output_codec = 'h264'
    encoder = av.codec.CodecContext.create(output_codec, 'w')
    encoder.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    encoder.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    encoder.pix_fmt = 'yuv420p'
    encoder.time_base = Fraction(1, 30)
    encoder.options = {
        'tune': 'zerolatency',
        'preset': 'ultrafast',
        'g': '30',  # GOP size of 1: all frames are I-frames
        'keyint_min': '30',  # Min: 1 I-frame every 30 frames
        'bf': '0',         # NO B-frames
        'flags': '+cgop',  # Closed GOP (optional, improves error resilience)
        'rc_lookahead': '0'  # Disable rate control lookahead for lower latency
    }

    start = time.time()
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Convert to AVFrame
        av_frame = av.VideoFrame.from_ndarray(frame, format='bgr24')
        av_frame = av_frame.reformat(format='yuv420p')

        # Encode
        packets = encoder.encode(av_frame)
        for pack in packets:
            if time.time() - start >= 1:
                print(i)
                start = time.time()
                i = 0
            payload = bytes(pack)
            # Create RTP packet
            pkt = RTPPacket(
                payload_type=PacketType.VIDEO.value,
                marker=True,
            )
            pkt.payload = payload

            with sender.send_lock:
                sender.send_queue.put(pkt)
            i += 1



main()

cv2.destroyAllWindows()