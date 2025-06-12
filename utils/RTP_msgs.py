
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


import struct
import time
from enum import Enum


class PacketType(Enum):
    VIDEO = 1
    AUDIO = 7


class RTPPacket:
    def __init__(self, version=0, padding=False, extension=False, marker=False, payload_type=PacketType.VIDEO.value,
                 sequence_number=0, ssrc=0, timestamp=None):
        """
        Initialize an RTP packet with optional header values

        :param version: RTP version number (default 0)
        :type version: int

        :param padding: whether the packet uses padding
        :type padding: bool

        :param extension: whether the packet has an extension header
        :type extension: bool

        :param marker: marker bit, often used to signal end of frame
        :type marker: bool

        :param payload_type: RTP payload type (e.g., video/audio type)
        :type payload_type: int

        :param sequence_number: packet sequence number
        :type sequence_number: int

        :param ssrc: synchronization source identifier
        :type ssrc: int

        :param timestamp: packet timestamp (defaults to current time if None)
        :type timestamp: int or None
        """
        self.version = version
        self.padding = padding
        self.extension = extension
        self.marker = marker
        self.payload_type = payload_type
        self.sequence_number = sequence_number % 0x10000
        self.ssrc = ssrc
        self.timestamp = self.timestamp = timestamp if timestamp is not None else int(time.time() * 1000) & 0xFFFFFFF

        self.cc = 0
        self.payload = b''

    def build_packet(self):
        """
        Build the RTP packet from header and payload

        :return: raw bytes of the RTP packet ready to be sent
        :rtype: bytes
        """
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
        """
        Set the payload data of the RTP packet

        :param payload: the raw payload data to include in the packet
        :type payload: bytes
        """
        # payload is bytes
        self.payload = payload

    def decode_packet(self, packet_bytes):
        """
        Decode an RTP packet and populate the object's attributes

        :param packet_bytes: the received RTP packet bytes
        :type packet_bytes: bytes

        :return: True if decoding succeeded, False if packet is malformed
        :rtype: bool
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
        """
        Return string representation of the packet for debugging

        :return: string with packet header info and payload length
        :rtype: str
        """
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
