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
    receiver = RTPHandler(send_ip='127.0.0.1', listen_port=2432, send_port=5006, msg_type=PacketType.VIDEO)
    receiver.start(receive=True, send=False)

    try:
        while True:
            if not receiver.receive_queue.empty():
                pkt = receiver.receive_queue.get()
                print(pkt)
                img_data = pkt.payload
                img_array = np.frombuffer(img_data, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                if frame is not None:
                    cv2.imshow('Received Stream', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        print("Receiver stopped.")
    finally:
        receiver.stop()
        cv2.destroyAllWindows()

receiver_main()
