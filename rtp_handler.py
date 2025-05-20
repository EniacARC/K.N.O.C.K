import queue
import random
import socket
import threading
import time

from RTP_msgs import *

MAX_PACKET_SIZE = int(1500)


class RTPHandler:

    def __init__(self, send_ip, listen_port, send_port):
        self.running = False
        self.send_ip = send_ip
        self.listen_port = listen_port
        self.send_port = send_port

        self.receive_lock = threading.Lock()

        # RTPPacket objs
        self.receive_queue = queue.Queue()
        self.recv_payload = None

        # should be thread safe if 1 thread is reading only and one is writing only
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 ** 20)

        self.receive_thread = None
        self.send_thread = None

        self.my_seq = random.randint(0, 50000)
        self.remote_seq = None
        # self.ssrc = random.randint(0, 50000) # will be selected from the sending thread

    def start(self, receive):
        if self.running:
            return

        self.running = True

        self.socket.bind(('0.0.0.0', self.listen_port))
        self.socket.settimeout(0.5)  # make sure we can check running flag

        if receive:
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.start()

        print(
            f"RTP Handler started - Listening on port {self.listen_port}, sending to {self.send_ip}:{self.send_port}")

    def stop(self):
        """Stop the RTP handler threads"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.socket.close()
        print("RTP Handler stopped")

    def send_packet(self, packet):
        """Thread function to send RTP packets"""
        try:
            # the sequence number is not controlled by the high logic but by transport logic, so it belongs here.
            # if random.randint(1, 100) == 2:
            #     print("dropped")
            #     self.my_seq += 1
            #     return

            # packet: RTPPacket
            packet.sequence_number = self.my_seq
            # if packet is bigger than mmu split packet
            pkts = self._build_packets(packet.ssrc, packet.payload)
            for pkt in pkts:
                self.socket.sendto(pkt.build_packet(), (self.send_ip, self.send_port))
                self.my_seq += 1
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
                    # self.receive_queue.put(data) # thread safe

                    # build fragmented packets, only add a full frame
                    packet = RTPPacket()
                    if packet.decode_packet(data):
                        # print(packet)
                        # Case 1: A previous frame is being built
                        if self.recv_payload:
                            # If the timestamp changed, drop the old frame
                            if packet.sequence_number != self.remote_seq:
                                print(f"Dropped incomplete frame: {self.recv_payload}")
                                self.recv_payload = None

                            # If packet belongs to current frame but is not the expected sequence number, drop frame
                            elif packet.sequence_number != self.remote_seq:
                                print(f"Missing packet, dropped frame: {self.recv_payload}")
                                self.recv_payload = None

                        # Continue based on whether this is a marker (last fragment) or not
                        if packet.marker:
                            if self.recv_payload:
                                # Append and complete the current frame
                                self.recv_payload.payload += packet.payload
                                self.receive_queue.put(self.recv_payload)
                                recv_payload = None
                            else:
                                # Full packet in one go, no fragmentation
                                self.receive_queue.put(self.recv_payload)
                        else:
                            # Intermediate or first fragment
                            if self.recv_payload:
                                # Append fragment
                                self.recv_payload.payload += packet.payload
                                self.remote_seq += 1
                            else:
                                # Start a new fragmented frame
                                self.recv_payload = packet
                                self.remote_seq = packet.sequence_number + 1

                except socket.timeout:
                    continue

                # Parse the received packet
            except Exception as e:
                print(f"Error in receive loop: {e}")


    def _build_packets(self, ssrc, payload):
        to_send = []
        timestamp = RTPPacket().timestamp
        m = RTPPacket()
        m.payload = payload
        # print(len(payload))
        if len(m.build_packet()) > MAX_PACKET_SIZE:
            header_size = len(RTPPacket().build_packet())
            # Set the max payload size that ensures the full packet stays within limit
            max_payload_size = MAX_PACKET_SIZE - header_size
            # print(max_payload_size)

            # Split the payload into safe-sized chunks
            payloads = [payload[i:i + max_payload_size] for i in
                        range(0, len(payload), max_payload_size)]
            # print(len(payloads))

            for payload1 in payloads[:-1]:  # All except the last
                packet = RTPPacket(
                    timestamp = timestamp,
                    ssrc = ssrc
                )
                packet.payload = payload1
                packet.marker = False
                to_send.append(packet)

            # Send the last payload with marker = True
            packet = RTPPacket(
                timestamp=timestamp,
                ssrc=ssrc
            )
            packet.payload = payloads[-1]
            packet.marker = True
            to_send.append(packet)
        else:
            packet = RTPPacket(
                timestamp = timestamp,
                ssrc = ssrc
            )
            packet.payload = payload
            to_send.append(packet)

        return to_send


# import time
#
#
# class RTPTimestampSync:
#     def __init__(self, clock_rate: int):
#         """
#         clock_rate: RTP clock rate (Hz), e.g., 90000 for video, 48000 for audio
#         """
#         self.clock_rate = clock_rate
#
#         # Choose a reference start time in seconds (wall clock)
#         # This will be the zero RTP timestamp reference point
#         self.start_time = time.time()
#
#         # Optionally: initial RTP timestamp (randomized or zero)
#         self.initial_timestamp = 0
#
#     def get_timestamp(self) -> int:
#         """
#         Returns the current RTP timestamp based on elapsed time scaled to clock rate
#         """
#         elapsed = time.time() - self.start_time
#         timestamp = int(elapsed * self.clock_rate)
#         return (self.initial_timestamp + timestamp) & 0xFFFFFFFF  # RTP timestamp is 32 bits
#
#
# # Usage example:
#
# video_sync = RTPTimestampSync(clock_rate=90000)  # Video RTP clock rate
# audio_sync = RTPTimestampSync(clock_rate=48000)  # Audio RTP clock rate
#
# # When you need to timestamp a packet:
# video_rtp_ts = video_sync.get_timestamp()
# audio_rtp_ts = audio_sync.get_timestamp()
