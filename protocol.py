"""
protocol.py - Binary Framed Network Protocol and Lossy Channel Simulator for Langent.

Provides packet framing with CRC32 integrity verification, sequence numbers,
and a lossy wireless transmission simulator to evaluate transmission reliability.
"""

import random
import struct
import zlib
from typing import BinaryIO, Dict, List, Optional, Tuple, Union

MAGIC_BYTES = b"LN"  # Langent Network protocol identifier
PROTOCOL_VERSION = 1

# Packet header format:
# Magic: 2 bytes ('LN')
# Version: 1 byte (uint8)
# Flags: 1 byte (uint8) -> bit 0: is_last_packet, bit 1: is_token_stream
# Sequence Number: 4 bytes (uint32)
# Payload Length: 2 bytes (uint16)
# Header total = 10 bytes
# Followed by:
# Payload: N bytes
# CRC32 Checksum: 4 bytes (uint32)
HEADER_STRUCT = struct.Struct(">2s B B I H")
CRC_STRUCT = struct.Struct(">I")

FLAG_LAST_PACKET = 0x01
FLAG_TOKEN_STREAM = 0x02


class Packet:
    """
    Structured packet frame with CRC32 integrity checking.
    """

    def __init__(
        self,
        seq_num: int,
        payload: bytes,
        is_last: bool = False,
        is_token_stream: bool = False,
    ):
        self.seq_num = seq_num
        self.payload = payload
        self.is_last = is_last
        self.is_token_stream = is_token_stream

    @property
    def flags(self) -> int:
        f = 0
        if self.is_last:
            f |= FLAG_LAST_PACKET
        if self.is_token_stream:
            f |= FLAG_TOKEN_STREAM
        return f

    def serialize(self) -> bytes:
        """Serialize packet into binary frame with CRC32."""
        header = HEADER_STRUCT.pack(
            MAGIC_BYTES,
            PROTOCOL_VERSION,
            self.flags,
            self.seq_num,
            len(self.payload),
        )
        body = header + self.payload
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return body + CRC_STRUCT.pack(crc)

    @classmethod
    def deserialize(cls, data: bytes) -> "Packet":
        """
        Deserialize and validate packet frame.
        Raises ValueError if invalid magic, version, length, or CRC failure.
        """
        min_len = HEADER_STRUCT.size + CRC_STRUCT.size
        if len(data) < min_len:
            raise ValueError(f"Packet data too short ({len(data)} < {min_len})")

        magic, version, flags, seq_num, payload_len = HEADER_STRUCT.unpack_from(data, 0)
        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic bytes: {magic}")
        if version != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {version}")

        expected_total = HEADER_STRUCT.size + payload_len + CRC_STRUCT.size
        if len(data) != expected_total:
            raise ValueError(
                f"Packet length mismatch: expected {expected_total}, got {len(data)}"
            )

        payload = data[HEADER_STRUCT.size : HEADER_STRUCT.size + payload_len]
        (received_crc,) = CRC_STRUCT.unpack_from(data, HEADER_STRUCT.size + payload_len)

        computed_crc = zlib.crc32(data[: HEADER_STRUCT.size + payload_len]) & 0xFFFFFFFF
        if computed_crc != received_crc:
            raise ValueError(
                f"CRC32 mismatch on packet #{seq_num}: computed {hex(computed_crc)}, got {hex(received_crc)}"
            )

        is_last = bool(flags & FLAG_LAST_PACKET)
        is_token = bool(flags & FLAG_TOKEN_STREAM)
        return cls(seq_num, payload, is_last=is_last, is_token_stream=is_token)


def fragment_payload(
    payload: bytes,
    max_payload_per_packet: int = 1400,
    is_token_stream: bool = False,
) -> List[Packet]:
    """
    Fragments a payload byte sequence into framed Packet objects.
    """
    if not payload:
        return [Packet(0, b"", is_last=True, is_token_stream=is_token_stream)]

    packets: List[Packet] = []
    total_len = len(payload)
    seq = 0
    for offset in range(0, total_len, max_payload_per_packet):
        chunk = payload[offset : offset + max_payload_per_packet]
        is_last = (offset + max_payload_per_packet) >= total_len
        packets.append(Packet(seq, chunk, is_last=is_last, is_token_stream=is_token_stream))
        seq += 1

    return packets


def reassemble_packets(packets: List[Packet]) -> bytes:
    """
    Reassembles ordered packets into original payload bytes.
    Verifies sequential order.
    """
    if not packets:
        return b""

    # Sort packets by sequence number
    sorted_pkts = sorted(packets, key=lambda p: p.seq_num)

    # Check for missing packets
    for i, pkt in enumerate(sorted_pkts):
        if pkt.seq_num != i:
            raise ValueError(f"Missing packet sequence: expected #{i}, found #{pkt.seq_num}")

    return b"".join(p.payload for p in sorted_pkts)


class LossyWirelessChannel:
    """
    Simulates a lossy wireless transmission medium with packet drop and corruption rates.
    """

    def __init__(
        self,
        drop_rate: float = 0.0,
        corruption_rate: float = 0.0,
        seed: Optional[int] = None,
    ):
        self.drop_rate = drop_rate
        self.corruption_rate = corruption_rate
        self.rng = random.Random(seed)

    def transmit(self, raw_frames: List[bytes]) -> Tuple[List[bytes], Dict[str, int]]:
        """
        Transmit packet frames through the lossy channel.

        Returns:
            Tuple of (received_frames, channel_stats).
        """
        received: List[bytes] = []
        dropped_count = 0
        corrupted_count = 0

        for frame in raw_frames:
            # Check for packet drop
            if self.rng.random() < self.drop_rate:
                dropped_count += 1
                continue

            # Check for bit/byte corruption
            frame_data = bytearray(frame)
            if self.rng.random() < self.corruption_rate and len(frame_data) > 0:
                corrupted_count += 1
                flip_idx = self.rng.randint(0, len(frame_data) - 1)
                frame_data[flip_idx] ^= 0xFF

            received.append(bytes(frame_data))

        stats = {
            "total_sent": len(raw_frames),
            "delivered": len(received),
            "dropped": dropped_count,
            "corrupted": corrupted_count,
        }
        return received, stats


def simulate_packet_transfer(
    payload: bytes,
    drop_rate: float = 0.0,
    corruption_rate: float = 0.0,
    max_packet_size: int = 1400,
    seed: Optional[int] = None,
) -> Dict[str, Union[int, float, bool]]:
    """
    Simulates sending a payload over a lossy framed packet channel.
    """
    packets = fragment_payload(payload, max_payload_per_packet=max_packet_size)
    wire_frames = [pkt.serialize() for pkt in packets]

    channel = LossyWirelessChannel(
        drop_rate=drop_rate, corruption_rate=corruption_rate, seed=seed
    )
    delivered_frames, channel_stats = channel.transmit(wire_frames)

    valid_packets: List[Packet] = []
    crc_errors = 0

    for frame in delivered_frames:
        try:
            pkt = Packet.deserialize(frame)
            valid_packets.append(pkt)
        except ValueError:
            crc_errors += 1

    can_reconstruct = False
    reassembled_data = b""

    try:
        reassembled_data = reassemble_packets(valid_packets)
        if len(valid_packets) == len(packets) and reassembled_data == payload:
            can_reconstruct = True
    except ValueError:
        can_reconstruct = False

    return {
        "payload_bytes": len(payload),
        "total_packets": len(packets),
        "packets_sent": channel_stats["total_sent"],
        "packets_dropped": channel_stats["dropped"],
        "packets_corrupted": channel_stats["corrupted"],
        "crc_errors_detected": crc_errors,
        "valid_packets_received": len(valid_packets),
        "reconstructed_successfully": can_reconstruct,
    }
