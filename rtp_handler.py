import queue
import random
import socket
import threading
import time

from RTP_msgs import *

MAX_PACKET_SIZE = int(1500)


class RTPHandler:

    def __init__(self, send_ip, listen_port, send_port, msg_type):
        self.running = False
        self.send_ip = send_ip
        self.listen_port = listen_port
        self.send_port = send_port

        self.msg_type = msg_type.value

        self.receive_lock = threading.Lock()

        # RTPPacket objs
        self.receive_queue = queue.Queue()
        self.recv_payload = None

        # should be thread safe if 1 thread is reading only and one is writing only
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.receive_thread = None
        self.send_thread = None

        self.my_seq = random.randint(0, 50000)
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
            packet.sequence_number = self.my_seq
            # if packet is bigger than mmu split packet
            data = packet.build_packet()
            # print(f"sending: {packet} to {self.send_ip}:{self.send_port}")
            self.socket.sendto(data, (self.send_ip, self.send_port))
            # time.sleep(0.003)
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
                except socket.timeout:
                    continue


                # Parse the received packet
                packet = RTPPacket()
                if packet.decode_packet(data):
                    if self.recv_payload and self.recv_payload.timestamp != packet.timestamp:
                        print("dropped")
                        # Timestamp mismatch: discard previous fragment
                        self.recv_payload = None
                    if packet.marker:
                        if self.recv_payload:
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
            except Exception as e:
                print(f"Error in receive loop: {e}")

    @staticmethod
    def build_packets(ssrc, payload):
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