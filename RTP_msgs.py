import datetime
import time
from platform import version

from uac2 import SERVER_PORT

class RTPPacket:
    def __init__(self, version, padding, marker, payload_type, ssrc, sequence_number, payload):
        self.version = version
        self.padding = padding
        self.marker = marker
        self.payload_type = payload_type
        self.ssrc = ssrc
        self.sequence_number = sequence_number
        self.timestamp = int(time.time() * 1000) & 0xFFFFFFFF  # Wraps around at 32 bits
        self.payload = payload

    def build_packet(self):
        csrc = 0
        cc = 0
        extension = 0

        # First byte: Version (2 bits), Padding (1 bit), Extension (1 bit), CSRC Count (4 bits)
        first_byte = (self.version << 6) | (self.padding << 5) | (extension << 4) | cc

        # Second byte: Marker (1 bit), Payload Type (7 bits)
        second_byte = (self.marker << 7) | self.payload_type

        # Sequence number (16 bits)
        seq_bytes = self.sequence_number.to_bytes(2, byteorder='big')

        # Timestamp (32 bits) - directly use the integer timestamp
        timestamp_bytes = self.timestamp.to_bytes(4, byteorder='big')

        # SSRC (32 bits)
        ssrc_bytes = self.ssrc.to_bytes(4, byteorder='big')

        # Combine all fields
        header = bytes([first_byte, second_byte]) + seq_bytes + timestamp_bytes + ssrc_bytes

        # Add payload
        packet = header + self.payload

        return packet

    @staticmethod
    def parse_packet(packet_bytes):
        # Ensure we have at least the minimum header size (12 bytes)
        if len(packet_bytes) < 12:
            raise ValueError("Packet too small to be a valid RTP packet")

        # Parse first byte
        first_byte = packet_bytes[0]
        version = (first_byte >> 6) & 0x03
        padding = (first_byte >> 5) & 0x01
        # Note: In build_packet, extension is set to 0 and cc is set to 0

        # Parse second byte
        second_byte = packet_bytes[1]
        marker = (second_byte >> 7) & 0x01
        payload_type = second_byte & 0x7F

        # Parse sequence number (bytes 2-3)
        sequence_number = int.from_bytes(packet_bytes[2:4], byteorder='big')

        # Parse timestamp (bytes 4-7)
        timestamp = int.from_bytes(packet_bytes[4:8], byteorder='big')

        # Parse SSRC (bytes 8-11)
        ssrc = int.from_bytes(packet_bytes[8:12], byteorder='big')

        # Extract payload (fixed 12-byte header since cc=0 and extension=0)
        payload = packet_bytes[12:]

        # Remove padding if present
        if padding and payload:
            padding_size = payload[-1]
            if padding_size <= len(payload):
                payload = payload[:-padding_size]

        # Create and return new RTP packet object
        packet = RTPPacket(version, padding, marker, payload_type, ssrc, sequence_number, payload)
        packet.timestamp = timestamp  # Override the auto-generated timestamp with the parsed one

        return packet
