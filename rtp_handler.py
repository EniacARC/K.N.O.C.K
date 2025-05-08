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
print("hello")