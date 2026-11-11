"""
simulation.py - Entropy-based Transmission Simulation for Langent.

Simulates Alice and Bob sharing a common entropy pool (via PRNG seed or raw file)
and attempting to compress/encode data transmissions as offset/length pointers into
the shared entropy, measuring empirical transmission overhead and feasibility.
"""

import os
import random
import struct
import time
from typing import BinaryIO, Dict, Generator, List, Optional, Tuple, Union


def generate_prng_entropy(seed: int, size: int) -> bytes:
    """
    Generate deterministic pseudo-random entropy bytes from an integer seed.
    Compatible with Python 3.8+ via getrandbits fallback if randbytes is absent.
    """
    rng = random.Random(seed)
    if hasattr(rng, "randbytes"):
        return rng.randbytes(size)
    return rng.getrandbits(size * 8).to_bytes(size, "big")


class EntropyStream:
    """
    Provides random access over an entropy buffer or binary stream.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.size = len(data)

    @classmethod
    def from_seed(cls, seed: int, size: int) -> "EntropyStream":
        return cls(generate_prng_entropy(seed, size))

    @classmethod
    def from_file(cls, path: str, max_bytes: Optional[int] = None) -> "EntropyStream":
        with open(path, "rb") as f:
            if max_bytes is not None:
                content = f.read(max_bytes)
            else:
                content = f.read()
        return cls(content)

    def slice(self, offset: int, length: int) -> bytes:
        if offset < 0 or offset + length > self.size:
            raise IndexError("Entropy slice out of bounds")
        return self.data[offset : offset + length]


class Token:
    """
    Transmission token sent across the wire.
    Can either be an entropy reference (offset, length) or a literal byte sequence.
    """

    TAG_POINTER = 0
    TAG_LITERAL = 1

    def __init__(
        self,
        tag: int,
        offset: int = 0,
        length: int = 0,
        literal_bytes: bytes = b"",
    ):
        self.tag = tag
        self.offset = offset
        self.length = length
        self.literal_bytes = literal_bytes

    def wire_size(self) -> int:
        """
        Calculates the wire size in bytes.
        Pointer format:
          1 byte tag (0) + 4 bytes offset (unsigned 32-bit int) + 2 bytes length (unsigned 16-bit int) = 7 bytes.
        Literal format:
          1 byte tag (1) + 2 bytes length (unsigned 16-bit int) + N literal payload bytes = 3 + N bytes.
        """
        if self.tag == self.TAG_POINTER:
            return 7
        else:
            return 3 + len(self.literal_bytes)

    def pack(self) -> bytes:
        """Serialize token into binary format for transmission."""
        if self.tag == self.TAG_POINTER:
            return struct.pack(">B I H", self.TAG_POINTER, self.offset, self.length)
        else:
            lit_len = len(self.literal_bytes)
            return struct.pack(f">B H {lit_len}s", self.TAG_LITERAL, lit_len, self.literal_bytes)

    @classmethod
    def unpack_from(cls, stream: BinaryIO) -> Optional["Token"]:
        """Deserialize token from a binary stream."""
        tag_bytes = stream.read(1)
        if not tag_bytes:
            return None
        tag = tag_bytes[0]
        if tag == cls.TAG_POINTER:
            buf = stream.read(6)
            if len(buf) < 6:
                raise ValueError("Corrupt pointer token in stream")
            offset, length = struct.unpack(">I H", buf)
            return cls(cls.TAG_POINTER, offset=offset, length=length)
        elif tag == cls.TAG_LITERAL:
            buf = stream.read(2)
            if len(buf) < 2:
                raise ValueError("Corrupt literal token header in stream")
            (lit_len,) = struct.unpack(">H", buf)
            lit_data = stream.read(lit_len)
            if len(lit_data) < lit_len:
                raise ValueError("Corrupt literal token body in stream")
            return cls(cls.TAG_LITERAL, literal_bytes=lit_data)
        else:
            raise ValueError(f"Unknown token tag: {tag}")

    def __repr__(self) -> str:
        if self.tag == self.TAG_POINTER:
            return f"Pointer(offset={self.offset}, len={self.length})"
        return f"Literal(len={len(self.literal_bytes)})"


def build_entropy_index(
    entropy: bytes, chunk_len: int = 4, step: int = 1
) -> Dict[bytes, List[int]]:
    """
    Builds a quick lookup index mapping k-byte substrings to their starting offsets in entropy.
    """
    index: Dict[bytes, List[int]] = {}
    n = len(entropy)
    for i in range(0, n - chunk_len + 1, step):
        key = entropy[i : i + chunk_len]
        if key not in index:
            index[key] = []
        index[key].append(i)
    return index


def encode_transmission(
    data: bytes,
    entropy: EntropyStream,
    min_match_len: int = 8,
    max_match_len: int = 65535,
    entropy_index: Optional[Dict[bytes, List[int]]] = None,
    index_prefix_len: int = 4,
) -> List[Token]:
    """
    Alice encodes data against shared entropy into a list of Tokens.
    Uses index-assisted greedy longest match search.
    """
    if entropy_index is None and len(entropy.data) > 0 and index_prefix_len <= len(entropy.data):
        entropy_index = build_entropy_index(entropy.data, chunk_len=index_prefix_len)

    tokens: List[Token] = []
    i = 0
    data_len = len(data)
    pending_literals = bytearray()

    def flush_literals():
        nonlocal pending_literals
        if pending_literals:
            # Emit literals in chunks if exceeding uint16 max length
            max_lit_len = 65535
            for start in range(0, len(pending_literals), max_lit_len):
                chunk = bytes(pending_literals[start : start + max_lit_len])
                tokens.append(Token(Token.TAG_LITERAL, literal_bytes=chunk))
            pending_literals = bytearray()

    while i < data_len:
        best_offset = -1
        best_len = 0

        # Try to find a match of at least min_match_len
        if entropy_index and (i + index_prefix_len <= data_len):
            prefix = data[i : i + index_prefix_len]
            candidate_offsets = entropy_index.get(prefix, [])

            for off in candidate_offsets:
                # Find extent of match
                max_possible = min(data_len - i, entropy.size - off, max_match_len)
                match_len = 0
                while match_len < max_possible and data[i + match_len] == entropy.data[off + match_len]:
                    match_len += 1

                if match_len > best_len:
                    best_len = match_len
                    best_offset = off
                    if best_len >= max_match_len:
                        break

        # Check if match meets minimum length threshold
        if best_len >= min_match_len:
            flush_literals()
            tokens.append(Token(Token.TAG_POINTER, offset=best_offset, length=best_len))
            i += best_len
        else:
            pending_literals.append(data[i])
            i += 1

    flush_literals()
    return tokens


def decode_transmission(tokens: List[Token], entropy: EntropyStream) -> bytes:
    """
    Bob decodes tokens back into original data using shared entropy.
    """
    out = bytearray()
    for token in tokens:
        if token.tag == Token.TAG_POINTER:
            out.extend(entropy.slice(token.offset, token.length))
        elif token.tag == Token.TAG_LITERAL:
            out.extend(token.literal_bytes)
        else:
            raise ValueError(f"Unknown token tag {token.tag}")
    return bytes(out)


def run_simulation(
    payload: bytes,
    entropy: EntropyStream,
    min_match_len: int = 8,
) -> Dict[str, Union[int, float, bool]]:
    """
    Executes a complete transmission simulation between Alice and Bob,
    returning performance and compression metrics.
    """
    start_time = time.perf_counter()
    tokens = encode_transmission(payload, entropy, min_match_len=min_match_len)
    encode_time = time.perf_counter() - start_time

    decode_start = time.perf_counter()
    reconstructed = decode_transmission(tokens, entropy)
    decode_time = time.perf_counter() - decode_start

    is_verified = (reconstructed == payload)
    raw_size = len(payload)
    wire_size = sum(token.wire_size() for token in tokens)

    pointer_tokens = [t for t in tokens if t.tag == Token.TAG_POINTER]
    literal_tokens = [t for t in tokens if t.tag == Token.TAG_LITERAL]

    pointer_covered_bytes = sum(t.length for t in pointer_tokens)
    literal_covered_bytes = sum(len(t.literal_bytes) for t in literal_tokens)

    compression_ratio = wire_size / raw_size if raw_size > 0 else 1.0

    return {
        "verified": is_verified,
        "raw_size": raw_size,
        "wire_size": wire_size,
        "compression_ratio": round(compression_ratio, 4),
        "pointer_tokens_count": len(pointer_tokens),
        "literal_tokens_count": len(literal_tokens),
        "pointer_covered_bytes": pointer_covered_bytes,
        "literal_covered_bytes": literal_covered_bytes,
        "entropy_pool_size": entropy.size,
        "encode_time_sec": round(encode_time, 4),
        "decode_time_sec": round(decode_time, 4),
    }
