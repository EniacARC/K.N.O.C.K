# import datetime
# import time
# from platform import version
# from enum import Enum
#
# import struct
# import random
#
#
# class RTPPacket:
#     """
#     A class for building and parsing RTP (Real-time Transport Protocol) packets.
#
#     RTP packet format:
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |V=2|P|X|  CC   |M|     PT      |       sequence number         |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                           timestamp                           |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |           synchronization source (SSRC) identifier            |
#    +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
#    |            contributing source (CSRC) identifiers             |
#    |                             ....                              |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                            payload                            |
#    |                             ....                              |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     """
#
#     # Common payload types (PT)
#     PT_PCMU = 0  # G.711 μ-law
#     PT_PCMA = 8  # G.711 A-law
#     PT_G722 = 9  # G.722
#     PT_H264 = 96  # H.264 video (dynamic)
#     PT_VP8 = 97  # VP8 video (dynamic)
#     PT_OPUS = 111  # Opus audio (dynamic)
#
#     def __init__(self, version=2, padding=False, extension=False, cc=0,
#                  marker=False, payload_type=0, sequence_number=None,
#                  timestamp=None, ssrc=None, csrc_list=None, payload=b''):
#         """
#         Initialize a new RTP packet.
#
#         Args:
#             version (int): RTP version, usually 2
#             padding (bool): Whether padding bits are present
#             extension (bool): Whether extension header is present
#             cc (int): CSRC count, number of CSRC identifiers
#             marker (bool): Marker bit, interpretation defined by profile
#             payload_type (int): Payload type identifier
#             sequence_number (int): Sequence number of this packet
#             timestamp (int): Sampling timestamp
#             ssrc (int): Synchronization source identifier
#             csrc_list (list): List of contributing source identifiers
#             payload (bytes): RTP payload data
#         """
#         self.version = version
#         self.padding = padding
#         self.extension = extension
#         self.cc = cc
#         self.marker = marker
#         self.payload_type = payload_type
#
#         # Generate random values if not provided
#         self.sequence_number = sequence_number if sequence_number is not None else random.randint(0, 65535)
#         self.timestamp = timestamp if timestamp is not None else int(time.time() * 1000) & 0xFFFFFFF
#         self.ssrc = ssrc if ssrc is not None else random.randint(0, 0xFFFFFFFF)
#
#         self.csrc_list = csrc_list if csrc_list is not None else []
#         if len(self.csrc_list) != self.cc:
#             self.cc = len(self.csrc_list)
#
#         self.payload = payload
#
#     def build(self):
#         """
#         Build a complete RTP packet.
#
#         Returns:
#             bytes: The complete RTP packet as bytes
#         """
#         # First byte: version (2 bits), padding (1 bit), extension (1 bit), CSRC count (4 bits)
#         first_byte = (self.version << 6) | (self.padding << 5) | (self.extension << 4) | (self.cc & 0x0F)
#
#         # Second byte: marker (1 bit), payload type (7 bits)
#         second_byte = (self.marker << 7) | (self.payload_type & 0x7F)
#
#         # Build the header
#         header = struct.pack('!BBHII',
#                              first_byte,
#                              second_byte,
#                              self.sequence_number,
#                              self.timestamp,
#                              self.ssrc)
#
#         # Add CSRC identifiers if any
#         for csrc in self.csrc_list:
#             header += struct.pack('!I', csrc)
#
#         # Combine header and payload
#         return header + self.payload
#
#     @classmethod
#     def parse(cls, packet_bytes):
#         """
#         Parse an RTP packet from bytes.
#
#         Args:
#             packet_bytes (bytes): The RTP packet bytes to parse
#
#         Returns:
#             RTPPacket: An RTP packet object
#         """
#         if len(packet_bytes) < 12:  # Minimum RTP header length
#             raise ValueError("Packet too short to be a valid RTP packet")
#
#         # Parse the first 12 bytes (fixed header)
#         first_byte, second_byte, seq_num, timestamp, ssrc = struct.unpack('!BBHII', packet_bytes[:12])
#
#         # Extract fields from first byte
#         version = (first_byte >> 6) & 0x03
#         padding = bool((first_byte >> 5) & 0x01)
#         extension = bool((first_byte >> 4) & 0x01)
#         cc = first_byte & 0x0F
#
#         # Extract fields from second byte
#         marker = bool((second_byte >> 7) & 0x01)
#         payload_type = second_byte & 0x7F
#
#         # Parse CSRC list if present
#         csrc_list = []
#         header_size = 12 + (4 * cc)
#
#         if len(packet_bytes) < header_size:
#             raise ValueError(f"Packet too short for {cc} CSRC identifiers")
#
#         for i in range(cc):
#             offset = 12 + (i * 4)
#             csrc = struct.unpack('!I', packet_bytes[offset:offset + 4])[0]
#             csrc_list.append(csrc)
#
#         # Extract the payload
#         payload = packet_bytes[header_size:]
#
#         # Create and return a new RTPPacket instance
#         return cls(
#             version=version,
#             padding=padding,
#             extension=extension,
#             cc=cc,
#             marker=marker,
#             payload_type=payload_type,
#             sequence_number=seq_num,
#             timestamp=timestamp,
#             ssrc=ssrc,
#             csrc_list=csrc_list,
#             payload=payload
#         )
#
#     def increment_sequence(self):
#         """Increment the sequence number, handling wrapping around 16 bits"""
#         self.sequence_number = (self.sequence_number + 1) & 0xFFFF
#         return self.sequence_number
#
#     def increment_timestamp(self, increment=1):
#         """
#         Increment the timestamp by the given value, handling wrapping around 32 bits
#
#         Args:
#             increment (int): Value to increment the timestamp by
#         """
#         self.timestamp = (self.timestamp + increment) & 0xFFFFFFFF
#         return self.timestamp
#
#     def __str__(self):
#         """Return a string representation of the RTP packet"""
#         return (f"RTP Packet:\n"
#                 f"  Version: {self.version}\n"
#                 f"  Padding: {self.padding}\n"
#                 f"  Extension: {self.extension}\n"
#                 f"  CSRC Count: {self.cc}\n"
#                 f"  Marker: {self.marker}\n"
#                 f"  Payload Type: {self.payload_type}\n"
#                 f"  Sequence Number: {self.sequence_number}\n"
#                 f"  Timestamp: {self.timestamp}\n"
#                 f"  SSRC: 0x{self.ssrc:08x}\n"
#                 f"  CSRC List: {[f'0x{csrc:08x}' for csrc in self.csrc_list]}\n"
#                 f"  Payload Length: {len(self.payload)} bytes")
#
#
# # Example usage
# # Create a new RTP packet
# rtp = RTPPacket(
#     payload_type=RTPPacket.PT_OPUS,
#     marker=True,
#     payload=b'Hello, RTP world!'
# )
#
# # Build the packet
# packet_bytes = rtp.build()
# print(f"Built packet: {len(packet_bytes)} bytes")
# print(len(packet_bytes))
#
# # Parse the packet back
# parsed_packet = RTPPacket.parse(packet_bytes)
# print("\nParsed packet:")
# print(parsed_packet)
#
# # Demonstrate sequence and timestamp incrementing
# rtp.increment_sequence()
# rtp.increment_timestamp(160)  # Common for audio (e.g., 20ms of 8kHz audio)
# print(f"\nAfter incrementing: seq={rtp.sequence_number}, ts={rtp.timestamp}")


import struct
import time
from enum import Enum


class PacketType(Enum):
    VIDEO = 1
    AUDIO = 7


class RTPPacket:
    def __init__(self, version=0, padding=False, extension=False, marker=False, payload_type=PacketType.VIDEO.value,
                 sequence_number=0, ssrc=0, timestamp=int(time.time() * 1000) & 0xFFFFFFF):
        self.version = version
        self.padding = padding
        self.extension = extension
        self.marker = marker
        self.payload_type = payload_type
        self.sequence_number = sequence_number
        self.ssrc = ssrc
        self.timestamp = timestamp

        self.cc = 0
        self.payload = b''

    def build_packet(self):

        # First byte: version (2 bits), padding (1 bit), extension (1 bit), CSRC count (4 bits)
        first_byte = (self.version << 6) | (self.padding << 5) | (self.extension << 4) | (self.cc & 0x0F)

        # Second byte: marker (1 bit), payload type (7 bits)
        second_byte = (self.marker << 7) | (self.payload_type & 0x7F)

        # Build the header
        header = struct.pack('!BBHII',
                             first_byte,
                             second_byte,
                             self.sequence_number,
                             self.timestamp,
                             self.ssrc)

        # Combine everything
        packet = header + self.payload
        # Add padding if requested
        if self.padding and len(packet) % 4 != 0:
            # Calculate how many padding bytes needed for 32-bit alignment
            padding_len = 4 - (len(packet) % 4)
            # Last byte of padding contains the number of padding bytes
            padding = bytes([0] * (padding_len - 1) + [padding_len])
            packet += padding
        return packet

    def set_payload(self, payload):
        # payload is bytes
        self.payload = payload

    def decode_packet(self, packet_bytes):
        """
        Decode an RTP packet and set the attributes accordingly.

        Args:
            packet_bytes (bytes): The RTP packet to decode

        Returns:
            bool: True if packet was successfully decoded, False otherwise
        """
        if len(packet_bytes) < 12:  # Minimum RTP header size
            return False

        # Unpack the fixed header (12 bytes)
        header = packet_bytes[:12]
        first_byte, second_byte, seq_num, ts, ssrc = struct.unpack('!BBHII', header)

        # Parse first byte
        self.version = (first_byte >> 6) & 0x03
        self.padding = bool((first_byte >> 5) & 0x01)
        self.extension = bool((first_byte >> 4) & 0x01)
        self.cc = first_byte & 0x0F

        # Parse second byte
        self.marker = bool((second_byte >> 7) & 0x01)
        self.payload_type = second_byte & 0x7F

        # Set other fields
        self.sequence_number = seq_num
        self.timestamp = ts
        self.ssrc = ssrc

        # Current position in the packet
        pos = 12

        # Calculate payload length, considering padding
        payload_end = len(packet_bytes)
        if self.padding:
            padding_size = packet_bytes[-1]
            if padding_size <= payload_end - pos:
                payload_end -= padding_size
            else:
                return False  # Invalid padding

        # Extract payload
        self.payload = packet_bytes[pos:payload_end]

        return True

    def __str__(self):
        """Return string representation of the packet for debugging"""
        return (f"RTP Packet: V={self.version}, P={self.padding}, X={self.extension}, "
                f"M={self.marker}, PT={self.payload_type}, Seq={self.sequence_number}, "
                f"TS={self.timestamp}, SSRC={self.ssrc}, "
                f"Payload length={len(self.payload)}")

# m = RTPPacket().build_packet()
# bits = []
# for b in m:
#     # Convert byte to 8-bit binary string, removing '0b' prefix
#     binary = format(b, '08b')
#     bits.append(binary)
# print(bits)
#
# m2 = RTPPacket()
# m2.decode_packet(m)
# print(str(m2))
