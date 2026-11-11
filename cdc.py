"""
cdc.py - Content-Defined Chunking (CDC) and Entropy Dictionary Deduplication.

Splits arbitrary binary data into variable-size chunks using a rolling polynomial
hash boundary (Rabin-style fingerprinting) and evaluates shared chunk overlap
against entropy pools.
"""

import hashlib
from typing import Dict, Generator, List, NamedTuple, Set, Tuple


class Chunk(NamedTuple):
    offset: int
    length: int
    digest: str  # SHA-256 hex digest
    data: bytes


def chunk_data(
    data: bytes,
    min_size: int = 64,
    avg_size: int = 256,
    max_size: int = 1024,
    mask: int = 0xFF,  # 256 average chunk boundary mask
) -> List[Chunk]:
    """
    Partition byte data into variable-sized chunks using a rolling hash boundary.
    """
    if not data:
        return []

    chunks: List[Chunk] = []
    n = len(data)
    start = 0

    # Rolling hash parameters
    window_size = 16
    radix = 256
    modulus = 2147483647
    h_multiplier = pow(radix, window_size - 1, modulus)

    while start < n:
        remaining = n - start
        if remaining <= min_size:
            chunk_bytes = data[start:n]
            digest = hashlib.sha256(chunk_bytes).hexdigest()
            chunks.append(Chunk(start, len(chunk_bytes), digest, chunk_bytes))
            break

        # Calculate initial rolling hash over the window
        eff_window = min(window_size, min_size)
        window_start = start + min_size - eff_window
        w_bytes = data[window_start : window_start + eff_window]
        h = 0
        for b in w_bytes:
            h = (radix * h + b) % modulus

        split_found = False
        limit = min(n, start + max_size)

        for curr_pos in range(start + min_size, limit):
            b_in = data[curr_pos]
            b_out = data[curr_pos - window_size]

            # Update rolling hash
            h = (h - h_multiplier * b_out) % modulus
            h = (h * radix + b_in) % modulus
            h = (h + modulus) % modulus

            # Check boundary condition
            if (h & mask) == 0:
                chunk_len = curr_pos - start + 1
                chunk_bytes = data[start : start + chunk_len]
                digest = hashlib.sha256(chunk_bytes).hexdigest()
                chunks.append(Chunk(start, chunk_len, digest, chunk_bytes))
                start = curr_pos + 1
                split_found = True
                break

        if not split_found:
            # Reached max_size or EOF without trigger
            chunk_len = min(max_size, remaining)
            chunk_bytes = data[start : start + chunk_len]
            digest = hashlib.sha256(chunk_bytes).hexdigest()
            chunks.append(Chunk(start, chunk_len, digest, chunk_bytes))
            start += chunk_len

    return chunks


def evaluate_chunk_overlap(
    payload: bytes,
    entropy: bytes,
    min_size: int = 64,
    avg_size: int = 256,
    max_size: int = 1024,
) -> Dict[str, object]:
    """
    Chunks both the payload and the entropy stream, and evaluates dictionary overlap
    and deduplication hit rate.
    """
    payload_chunks = chunk_data(payload, min_size=min_size, avg_size=avg_size, max_size=max_size)
    entropy_chunks = chunk_data(entropy, min_size=min_size, avg_size=avg_size, max_size=max_size)

    entropy_digests: Set[str] = {c.digest for c in entropy_chunks}

    matched_chunks = 0
    matched_bytes = 0

    for c in payload_chunks:
        if c.digest in entropy_digests:
            matched_chunks += 1
            matched_bytes += c.length

    total_chunks = len(payload_chunks)
    total_bytes = len(payload)
    chunk_hit_ratio = matched_chunks / total_chunks if total_chunks > 0 else 0.0
    byte_hit_ratio = matched_bytes / total_bytes if total_bytes > 0 else 0.0

    return {
        "payload_bytes": total_bytes,
        "payload_chunks": total_chunks,
        "entropy_chunks": len(entropy_chunks),
        "matched_chunks": matched_chunks,
        "matched_bytes": matched_bytes,
        "chunk_hit_ratio": round(chunk_hit_ratio, 4),
        "byte_hit_ratio": round(byte_hit_ratio, 4),
    }
