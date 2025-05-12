# import queue
# from collections import defaultdict
#
#
# class RTPHandler:
#     def __init__(self, max_queue_size=100):
#         """
#         Initialize the RTP Handler.
#
#         Args:
#             max_queue_size: Maximum number of complete frames to store in the queue.
#         """
#         self.frame_queue = queue.Queue(maxsize=max_queue_size)
#         self.current_packets = defaultdict(dict)  # {timestamp: {sequence_number: packet}}
#         self.current_timestamp = None
#         self.expected_packets = {}  # {timestamp: expected_count}
#
#     def receive_packet(self, packet_bytes):
#         """
#         Receive and process an RTP packet.
#
#         Args:
#             packet_bytes: Raw bytes of the RTP packet.
#
#         Returns:
#             True if a complete frame was added to the queue, False otherwise.
#         """
#         try:
#             # Parse the incoming packet
#             packet = RTPPacket.parse_packet(packet_bytes)
#
#             # Check if this is from a new timestamp
#             if self.current_timestamp is not None and packet.timestamp > self.current_timestamp:
#                 # Drop all packets from the previous timestamp
#                 self._drop_current_frame()
#
#             # Update current timestamp
#             self.current_timestamp = packet.timestamp
#
#             # Store the packet
#             self.current_packets[packet.timestamp][packet.sequence_number] = packet
#
#             # Check if we have a complete frame
#             complete = self._check_complete_frame(packet.timestamp)
#             if complete:
#                 self._add_frame_to_queue(packet.timestamp)
#                 return True
#
#             return False
#
#         except ValueError as e:
#             print(f"Error processing packet: {e}")
#             return False
#
#     def _check_complete_frame(self, timestamp):
#         """
#         Check if all packets for a frame have been received.
#
#         This is a simplified implementation that assumes the marker bit is set
#         on the last packet of a frame.
#
#         Args:
#             timestamp: The timestamp to check.
#
#         Returns:
#             True if the frame is complete, False otherwise.
#         """
#         packets = self.current_packets[timestamp]
#
#         # Look for a packet with the marker bit set
#         for packet in packets.values():
#             if packet.marker:
#                 # Count the expected number of packets based on sequence numbers
#                 seq_numbers = sorted(packets.keys())
#
#                 # If we have a continuous sequence of packets up to the marked packet
#                 expected_count = max(seq_numbers) - min(seq_numbers) + 1
#                 self.expected_packets[timestamp] = expected_count
#
#                 # Check if we have all expected packets
#                 return len(packets) == expected_count
#
#         # No marker bit found yet or incomplete frame
#         return False
#
#     def _add_frame_to_queue(self, timestamp):
#         """
#         Assemble a complete frame and add it to the queue.
#
#         Args:
#             timestamp: The timestamp of the frame to add.
#         """
#         packets = self.current_packets[timestamp]
#
#         # Sort packets by sequence number
#         sorted_packets = [packets[seq] for seq in sorted(packets.keys())]
#
#         # Combine payloads
#         frame_data = b''.join(packet.payload for packet in sorted_packets)
#
#         # Add to queue
#         try:
#             self.frame_queue.put_nowait(frame_data)
#         except queue.Full:
#             # If queue is full, remove the oldest frame and try again
#             self.frame_queue.get()
#             self.frame_queue.put(frame_data)
#
#         # Clear the processed packets
#         del self.current_packets[timestamp]
#         del self.expected_packets[timestamp]
#
#     def _drop_current_frame(self):
#         """
#         Drop all packets from the current timestamp.
#         """
#         if self.current_timestamp is not None:
#             del self.current_packets[self.current_timestamp]
#             if self.current_timestamp in self.expected_packets:
#                 del self.expected_packets[self.current_timestamp]
#             self.current_timestamp = None
#
#     def get_frame(self, block=True, timeout=None):
#         """
#         Get the next complete frame from the queue.
#
#         Args:
#             block: If True, block until a frame is available.
#             timeout: If block is True, block for at most timeout seconds.
#
#         Returns:
#             Complete frame data as bytes, or None if no frame is available.
#         """
#         try:
#             return self.frame_queue.get(block=block, timeout=timeout)
#         except queue.Empty:
#             return None
#
#     def has_frame(self):
#         """
#         Check if there's a complete frame available.
#
#         Returns:
#             True if a frame is available, False otherwise.
#         """
#         return not self.frame_queue.empty()
import queue
import random
import socket
import threading
from RTP_msgs import *

MAX_PACKET_SIZE = int(1500 / 8)


class RTPHandler:

    def __init__(self, send_ip, listen_port, send_port, msg_type):
        self.send_ip = send_ip
        self.listen_port = listen_port
        self.send_port = send_port

        self.msg_type = msg_type.value

        self.send_lock = threading.Lock()
        self.receive_lock = threading.Lock()

        # RTPPacket objs
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.recv_payload = None

        self.running = False

        # should be thread safe if 1 thread is reading only and one is writing only
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.receive_thread = None
        self.send_thread = None

        self.my_seq = random.randint(0, 50000)
        # self.ssrc = random.randint(0, 50000) # will be selected from the sending thread

    def start(self, receive, send):
        if self.running:
            return

        self.running = True

        self.socket.bind(('0.0.0.0', self.listen_port))
        self.socket.settimeout(0.5)  # make sure we can check running flag

        if receive:
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.start()
        if send:
            self.send_thread = threading.Thread(target=self._send_loop)
            self.send_thread.start()
        print(
            f"RTP Handler started - Listening on port {self.listen_port}, sending to {self.send_ip}:{self.send_port}")

    def stop(self):
        """Stop the RTP handler threads"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
        self.socket.close()
        print("RTP Handler stopped")

    def _send_loop(self):
        """Thread function to send RTP packets"""
        while self.running:
            # print("running!")
            try:
                # Try to get a packet from the queue with timeout
                try:
                    with self.send_lock:
                        packet = self.send_queue.get(timeout=0.5)
                        print(packet)
                except queue.Empty:
                    continue

                # the sequence number is not controlled by the high logic but by transport logic, so it belongs here.
                packet.sequence_number = self.my_seq
                # if packet is bigger than mmu split packet
                data = packet.build_packet()
                if self.msg_type == PacketType.VIDEO.value and len(data) > MAX_PACKET_SIZE:
                    print("too big!")
                    packet.marker = False
                    payload_all = packet.payload
                    packet.payload = b''
                    header_size = len(packet.build_packet())
                    # Set the max payload size that ensures the full packet stays within limit
                    max_payload_size = MAX_PACKET_SIZE - header_size
                    # print(max_payload_size)

                    # Split the payload into safe-sized chunks
                    payloads = [payload_all[i:i + max_payload_size] for i in range(0, len(payload_all), max_payload_size)]
                    print(payloads)

                    for payload in payloads[:-1]:  # All except the last
                        packet.payload = payload
                        packet.marker = False
                        data = packet.build_packet()
                        self.socket.sendto(data, (self.send_ip, self.send_port))
                        self.my_seq += 1
                        packet.sequence_number += 1

                    # Send the last payload with marker = True
                    packet.payload = payloads[-1]
                    packet.marker = True
                    data = packet.build_packet()
                    self.socket.sendto(data, (self.send_ip, self.send_port))
                    self.my_seq += 1
                    packet.sequence_number += 1
                else:
                    print(f"sending: {data} to {self.send_ip}:{self.send_port}")
                    self.socket.sendto(data, (self.send_ip, self.send_port))
                    self.my_seq += 1
                # self.send_queue.task_done() ??
            except Exception as e:
                print(f"Error in send loop: {e}")

    def _receive_loop(self):
        """Thread function to receive RTP packets"""
        while self.running:
            try:
                # Set a timeout so we can check running flag periodically
                self.socket.settimeout(0.5)

                try:
                    data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)  # Max UDP packet size
                except socket.timeout:
                    continue

                # Parse the received packet
                packet = RTPPacket()
                if packet.decode_packet(data):
                    if self.msg_type == PacketType.VIDEO.value:
                        if self.recv_payload and self.recv_payload.timestamp != packet.timestamp:
                            # Timestamp mismatch: discard previous fragment
                            self.recv_payload = None
                        if packet.marker:
                            if self.recv_payload:
                                # if it's not none then timestamps must match
                                self.recv_payload.payload += packet.payload
                                with self.receive_lock:
                                    self.receive_queue.put(self.recv_payload)
                                self.recv_payload = None
                            else:
                                # No ongoing fragment or mismatch, queue this as a full packet
                                with self.receive_lock:
                                    self.receive_queue.put(packet)
                        else:
                            # Intermediate fragment
                            if self.recv_payload:
                                # if it's not none then timestamps must match
                                # Continue building the current payload
                                self.recv_payload.payload += packet.payload
                            else:
                                # Start a new fragmented payload
                                self.recv_payload = packet
                    else:
                        with self.receive_lock:
                            self.receive_queue.put(packet)
            except Exception as e:
                print(f"Error in receive loop: {e}")
