# import cv2
# import threading
# import queue
# import time
# from fractions import Fraction
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
# import av
#
# WIDTH, HEIGHT = 640, 480
# FPS = 30
#
# class FrameGrabber(threading.Thread):
#     def __init__(self, frame_queue):
#         super().__init__()
#         self.cap = cv2.VideoCapture(0)
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#         self.cap.set(cv2.CAP_PROP_FPS, FPS)
#         self.frame_queue = frame_queue
#         self.running = True
#
#     def run(self):
#         while self.running:
#             ret, frame = self.cap.read()
#             if not ret:
#                 continue
#             try:
#                 self.frame_queue.put(frame, timeout=0.1)
#             except queue.Full:
#                 # drop frame if queue full
#                 pass
#
#     def stop(self):
#         self.running = False
#         self.cap.release()
#
# class EncoderThread(threading.Thread):
#     def __init__(self, frame_queue, packet_queue):
#         super().__init__()
#         self.frame_queue = frame_queue
#         self.packet_queue = packet_queue
#         self.encoder = av.codec.CodecContext.create('h264', 'w')
#         self.encoder.width = WIDTH
#         self.encoder.height = HEIGHT
#         self.encoder.pix_fmt = 'yuv420p'
#         self.encoder.time_base = Fraction(1, FPS)
#         self.encoder.options = {
#             'tune': 'zerolatency',
#             'preset': 'ultrafast',
#             'g': '30',
#             'bf': '0',
#             'flags': '+cgop',
#             'rc_lookahead': '0',
#         }
#         self.frame_count = 0
#         self.running = True
#
#         # FPS measurement
#         self.fps_count = 0
#         self.fps_start_time = time.time()
#
#     def run(self):
#         while self.running:
#             try:
#                 frame = self.frame_queue.get(timeout=0.5)
#             except queue.Empty:
#                 continue
#
#             av_frame = av.VideoFrame.from_ndarray(frame, format='bgr24').reformat(format='yuv420p')
#             av_frame.pts = self.frame_count
#             packets = self.encoder.encode(av_frame)
#             for packet in packets:
#                 pkt = RTPPacket(
#                     payload_type=PacketType.VIDEO.value,
#                     marker=True,
#                     timestamp=int(self.frame_count * (90000 / FPS))
#                 )
#                 pkt.payload = bytes(packet)
#                 try:
#                     self.packet_queue.put_nowait(pkt)
#                 except queue.Full:
#                     pass
#
#             self.frame_count += 1
#             self.fps_count += 1
#
#             # Print FPS every second
#             elapsed = time.time() - self.fps_start_time
#             if elapsed >= 1.0:
#                 print(f"Encoding FPS: {self.fps_count / elapsed:.2f}")
#                 self.fps_start_time = time.time()
#                 self.fps_count = 0
#
#     def stop(self):
#         self.running = False
#         self.encoder.close()
#
# class SenderThread(threading.Thread):
#     def __init__(self, packet_queue, sender):
#         super().__init__()
#         self.packet_queue = packet_queue
#         self.sender = sender
#         self.running = True
#
#     def run(self):
#         while self.running:
#             try:
#                 pkt = self.packet_queue.get(timeout=0.5)
#                 with self.sender.send_lock:
#                     self.sender.send_queue.put_nowait(pkt)
#             except queue.Empty:
#                 continue
#
#     def stop(self):
#         self.running = False
#
# def main():
#     frame_queue = queue.Queue(maxsize=10)
#     packet_queue = queue.Queue(maxsize=30)
#
#     sender = RTPHandler(send_ip='127.0.0.1', listen_port=5006, send_port=2432, msg_type=PacketType.VIDEO)
#     sender.start(receive=False, send=True)
#
#     grabber = FrameGrabber(frame_queue)
#     encoder = EncoderThread(frame_queue, packet_queue)
#     sender_thread = SenderThread(packet_queue, sender)
#
#     grabber.start()
#     encoder.start()
#     sender_thread.start()
#
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("Stopping sender...")
#     finally:
#         grabber.stop()
#         encoder.stop()
#         sender_thread.stop()
#         sender.stop()
#
# if __name__ == "__main__":
#     main()


#
# import cv2
# import time
# import numpy as np
# import random
# import subprocess
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
#
# import threading
# import queue
#
# # Configuration
# SEND_IP = "127.0.0.1"
# LISTEN_PORT = 5006
# SEND_PORT = 2432
# FRAME_RATE = 30
# WIDTH, HEIGHT = 640, 480
# MAX_PACKET_SIZE = 1400  # Bytes, respecting MTU
#
# def create_ffmpeg_encoder():
#     """Create a persistent FFmpeg process for H.264 encoding."""
#     cmd = [
#         'ffmpeg',
#         '-f', 'rawvideo',
#         '-pix_fmt', 'rgb24',
#         '-s', f'{WIDTH}x{HEIGHT}',
#         '-r', str(FRAME_RATE),
#         '-i', 'pipe:',
#         '-c:v', 'libx264',
#         '-preset', 'ultrafast',
#         '-tune', 'zerolatency',
#         '-crf', '23',
#         '-threads', '4',
#         '-f', 'h264',
#         'pipe:'
#     ]
#     process = subprocess.Popen(
#         cmd,
#         stdin=subprocess.PIPE,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         bufsize=10**8
#     )
#     return process
#
# def fragment_nal_units(h264_data, max_packet_size):
#     """Fragment H.264 NAL units into RTP payloads."""
#     packets = []
#     start = 0
#     while start < len(h264_data):
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
#             packets.append(nal_unit)
#         else:
#             nal_type = nal_unit[nal_start+3 if nal_start+3 < len(nal_unit) else 0] & 0x1F
#             fu_payload = nal_unit[nal_start+4 if nal_start+4 < len(nal_unit) else nal_start+3:]
#             offset = 0
#             while offset < len(fu_payload):
#                 chunk_size = min(max_packet_size - 3, len(fu_payload) - offset)
#                 fu_indicator = (0x1C << 3) | (nal_type & 0x1F)
#                 fu_header = 0
#                 if offset == 0:
#                     fu_header |= 0x80
#                 if offset + chunk_size >= len(fu_payload):
#                     fu_header |= 0x40
#                 fu_header |= (nal_type & 0x1F)
#                 packet = bytearray([fu_indicator, fu_header]) + fu_payload[offset:offset+chunk_size]
#                 packets.append(bytes(packet))
#                 offset += chunk_size
#
#         start = next_nal
#
#     return packets
#
#
# def reader_thread(stdout, output_queue):
#     while True:
#         chunk = stdout.read(4096)
#         if not chunk:
#             break
#         output_queue.put(chunk)
#     output_queue.put(None)  # Signal EOF
#
# def main():
#
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
#     encoder = create_ffmpeg_encoder()
#     output_queue = queue.Queue()
#     thread = threading.Thread(target=reader_thread, args=(encoder.stdout, output_queue))
#     thread.daemon = True
#     thread.start()
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
#     clock_rate = 90000
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
#             # Write frame to FFmpeg stdin
#             encoder.stdin.write(frame_rgb.tobytes())
#             encoder.stdin.flush()
#
#             # Read encoded data from FFmpeg stdout
#             packets = []
#             while True:
#                 try:
#                     chunk = output_queue.get_nowait()
#                 except queue.Empty:
#                     # No data available right now — do other work, then try again later
#                     break
#                 if chunk is None:
#                     # EOF reached
#                     break
#                 packets.extend(fragment_nal_units(chunk, MAX_PACKET_SIZE))
#
#             # Send RTP packets
#             timestamp = int((time.time() - start_time) * clock_rate)
#             for i, payload in enumerate(packets):
#                 rtp_packet = RTPPacket()
#                 print(rtp_packet)
#                 rtp_packet.payload = payload
#                 rtp_packet.timestamp = timestamp
#                 rtp_packet.seq_num = seq_num
#                 rtp_packet.marker = (i == len(packets) - 1)
#                 rtp_packet.ssrc = ssrc
#                 rtp_packet.payload_type = PacketType.VIDEO.value
#
#                 try:
#                     with rtp_handler.send_lock:
#                         rtp_handler.send_queue.put(rtp_packet)
#                 except:
#                     pass
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
#             time.sleep(1 / FRAME_RATE)
#
#     except KeyboardInterrupt:
#         print("Stopping sender...")
#     finally:
#         cap.release()
#         encoder.stdin.close()
#         encoder.stdout.close()
#         encoder.terminate()
#         rtp_handler.stop()
#
# if __name__ == "__main__":
#     main()

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

# ------------------------------------------
#uses threads for speed
# ~20fps but can't connect in the middle?

# import cv2
# import time
# import av
# import threading
# import queue
# from fractions import Fraction
# from RTP_msgs import RTPPacket, PacketType
# from rtp_handler import RTPHandler
#
# # Configuration
# SEND_IP = "127.0.0.1"  # Destination IP
# LISTEN_PORT = 5006  # Port to listen on
# SEND_PORT = 2432  # Port to send RTP packets to
# TARGET_FPS = 30  # Target framerate
# WIDTH = 680  # Video width (reduced for performance)
# HEIGHT = 640  # Video height (reduced for performance)
# JPEG_QUALITY = 80  # JPEG compression quality (1-100)
#
#
# class EncoderThread(threading.Thread):
#     def __init__(self, frame_queue, packet_queue):
#         threading.Thread.__init__(self)
#         self.frame_queue = frame_queue
#         self.packet_queue = packet_queue
#         self.running = True
#         self.frame_count = 0
#
#         # Initialize encoder
#         self.output_codec = 'h264'
#         self.encoder = av.codec.CodecContext.create(self.output_codec, 'w')
#         self.encoder.width = WIDTH
#         self.encoder.height = HEIGHT
#         self.encoder.pix_fmt = 'yuv420p'
#         self.encoder.time_base = Fraction(1, TARGET_FPS)
#         self.encoder.options = {
#             'tune': 'zerolatency',
#             'preset': 'ultrafast',
#             'profile': 'baseline',  # Use baseline profile for compatibility
#             'g': '30',  # GOP size: I-frame every 15 frames
#             'bf': '0',  # No B-frames
#             'flags': '+cgop',  # Closed GOP
#             'rc_lookahead': '0',  # No lookahead
#             'crf': '30',  # Constant Rate Factor - higher value = lower quality/size
#             'threads': '4'  # Use multiple threads
#         }
#
#     def run(self):
#         print("Encoder thread started")
#         try:
#             while self.running:
#                 try:
#                     # Get frame with a timeout
#                     frame = self.frame_queue.get(timeout=0.5)
#
#                     # Convert to PyAV frame
#                     av_frame = av.VideoFrame.from_ndarray(frame, format='bgr24')
#                     av_frame = av_frame.reformat(format='yuv420p')
#                     av_frame.pts = self.frame_count
#
#                     # Encode frame
#                     packets = self.encoder.encode(av_frame)
#                     for packet in packets:
#                         payload = bytes(packet)
#
#                         # Create RTP packet
#                         rtp_packet = RTPPacket(
#                             payload_type=PacketType.VIDEO.value,
#                             marker=True,
#                             timestamp=int(self.frame_count * (90000 / TARGET_FPS))
#                         )
#                         rtp_packet.payload = payload
#
#                         # Add to packet queue
#                         try:
#                             self.packet_queue.put_nowait(rtp_packet)
#                         except queue.Full:
#                             pass  # Drop if queue is full
#
#                     self.frame_count += 1
#
#                 except queue.Empty:
#                     continue  # No frame available
#         except Exception as e:
#             print(f"Encoder thread error: {e}")
#         finally:
#             print("Encoder thread stopped")
#             self.encoder.close()
#
#     def stop(self):
#         self.running = False
#         self.join(timeout=1.0)
#
#
# class JPEGEncoderThread(threading.Thread):
#     def __init__(self, frame_queue, packet_queue):
#         threading.Thread.__init__(self)
#         self.frame_queue = frame_queue
#         self.packet_queue = packet_queue
#         self.running = True
#         self.frame_count = 0
#
#     def run(self):
#         print("JPEG encoder thread started")
#         try:
#             while self.running:
#                 try:
#                     # Get frame with a timeout
#                     frame = self.frame_queue.get(timeout=0.5)
#
#                     # Encode as JPEG (much faster than H.264)
#                     encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
#                     result, jpeg_data = cv2.imencode('.jpg', frame, encode_param)
#
#                     if result:
#                         # Create RTP packet
#                         rtp_packet = RTPPacket(
#                             payload_type=PacketType.VIDEO.value,
#                             marker=True,
#                             timestamp=int(self.frame_count * (90000 / TARGET_FPS))
#                         )
#                         rtp_packet.payload = jpeg_data.tobytes()
#
#                         # Add to packet queue
#                         try:
#                             self.packet_queue.put_nowait(rtp_packet)
#                         except queue.Full:
#                             pass  # Drop if queue is full
#
#                     self.frame_count += 1
#
#                 except queue.Empty:
#                     continue  # No frame available
#         except Exception as e:
#             print(f"JPEG encoder thread error: {e}")
#         finally:
#             print("JPEG encoder thread stopped")
#
#     def stop(self):
#         self.running = False
#         self.join(timeout=1.0)
#
#
# class SenderThread(threading.Thread):
#     def __init__(self, packet_queue, sender):
#         threading.Thread.__init__(self)
#         self.packet_queue = packet_queue
#         self.sender = sender
#         self.running = True
#         self.packets_sent = 0
#         self.start_time = time.time()
#
#     def run(self):
#         print("Sender thread started")
#         try:
#             while self.running:
#                 try:
#                     # Get packet with a timeout
#                     packet = self.packet_queue.get(timeout=0.5)
#
#                     # Send packet
#                     with self.sender.send_lock:
#                         self.sender.send_queue.put_nowait(packet)
#
#                     self.packets_sent += 1
#
#                     # Print statistics every second
#                     elapsed = time.time() - self.start_time
#                     if elapsed >= 1.0:
#                         print(
#                             f"Sent {self.packets_sent} packets in {elapsed:.2f}s ({self.packets_sent / elapsed:.2f} packets/s)")
#                         self.packets_sent = 0
#                         self.start_time = time.time()
#
#                 except queue.Empty:
#                     continue  # No packet available
#         except Exception as e:
#             print(f"Sender thread error: {e}")
#         finally:
#             print("Sender thread stopped")
#
#     def stop(self):
#         self.running = False
#         self.join(timeout=1.0)
#
#
# def main():
#     # Create queues
#     frame_queue = queue.Queue(maxsize=10)  # Small queue to avoid latency
#     packet_queue = queue.Queue(maxsize=30)
#
#     # Open webcam with OpenCV
#     cap = cv2.VideoCapture(0)  # Change index if needed
#
#     # Set camera properties
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
#     cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
#
#     # Get actual camera properties (may differ from requested)
#     actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     actual_fps = cap.get(cv2.CAP_PROP_FPS)
#     print(f"Camera: {actual_width}x{actual_height} @ {actual_fps} FPS")
#
#     # Initialize RTP sender
#     sender = RTPHandler(send_ip=SEND_IP, listen_port=LISTEN_PORT, send_port=SEND_PORT, msg_type=PacketType.VIDEO)
#     sender.start(receive=False, send=True)
#
#     # Choose encoder based on performance needs
#     use_jpeg = True  # JPEG is much faster than H.264, switch to False if you need H.264
#
#     # Create and start threads
#     if use_jpeg:
#         encoder_thread = JPEGEncoderThread(frame_queue, packet_queue)
#     else:
#         encoder_thread = EncoderThread(frame_queue, packet_queue)
#
#     sender_thread = SenderThread(packet_queue, sender)
#
#     encoder_thread.start()
#     sender_thread.start()
#
#     # Frame rate control variables
#     frame_time = 1.0 / TARGET_FPS  # Time per frame in seconds
#     next_frame_time = time.time()  # Time when next frame should be processed
#
#     # Statistics variables
#     stats_start_time = time.time()
#     frame_count = 0
#
#     try:
#         print(f"Starting video stream at {TARGET_FPS} FPS...")
#
#         while True:
#             try:
#                 # Capture frame without waiting for timing
#                 ret, frame = cap.read()
#                 if not ret:
#                     print("Failed to capture frame, retrying...")
#                     time.sleep(0.01)
#                     continue
#
#                 # Add frame to queue for processing (non-blocking)
#                 try:
#                     frame_queue.put_nowait(frame)
#                     frame_count += 1
#                 except queue.Full:
#                     # If queue is full, drop this frame
#                     pass
#
#                 # Track FPS
#                 current_time = time.time()
#                 elapsed = current_time - stats_start_time
#                 if elapsed >= 1.0:
#                     fps = frame_count / elapsed
#                     print(f"Capturing at {fps:.2f} FPS (target: {TARGET_FPS})")
#                     frame_count = 0
#                     stats_start_time = current_time
#
#                 # Wait just enough to maintain frame rate, if we're ahead of schedule
#                 wait_time = next_frame_time - time.time()
#                 if wait_time > 0:
#                     time.sleep(wait_time)
#
#                 # Schedule next frame
#                 next_frame_time = time.time() + frame_time
#
#             except KeyboardInterrupt:
#                 break
#             except Exception as e:
#                 print(f"Error in main loop: {e}")
#
#     finally:
#         # Clean up
#         print("Stopping stream and releasing resources...")
#         encoder_thread.stop()
#         sender_thread.stop()
#         cap.release()
#         sender.stop()
#         print("Stream stopped.")
#
#
# if __name__ == "__main__":
#     main()
#
# if __name__ == "__main__":
#     main()
# ------------------------------------------

import cv2
from imutils.video import VideoStream
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
    # Start threaded video capture
    vs = VideoStream(src=0).start()

    # Wait a bit for camera to warm up
    import time
    time.sleep(2.0)
    # Open webcam with OpenCV
    sender = RTPHandler(send_ip='127.0.0.1', listen_port=5006, send_port=2432, msg_type=PacketType.VIDEO)
    sender.start(receive=False, send=True)
    frame = vs.read()
    height, width = frame.shape[:2]

    # Encoder setup (H.264)
    output_codec = 'h264'
    encoder = av.codec.CodecContext.create(output_codec, 'w')
    encoder.width = width
    encoder.height = height
    encoder.pix_fmt = 'yuv420p'
    encoder.time_base = Fraction(1, 30)
    encoder.options = {
        'tune': 'zerolatency',
        'preset': 'ultrafast',
        #mabye 60?
        'g': '30',  # GOP size of 1: all frames are I-frames
        'keyint_min': '30',  # Min: 1 I-frame every 30 frames
        'bf': '0',         # NO B-frames
        'flags': '+cgop',  # Closed GOP (optional, improves error resilience)
        'rc_lookahead': '0',  # Disable rate control lookahead for lower latency
        'me': 'hex',
        # mabye turn off
        'crf': '26',  # Constant Rate Factor - higher value = lower quality/size
    }

    start = time.time()
    i = 0
    while True:
        frame = vs.read()
        if frame is None:
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