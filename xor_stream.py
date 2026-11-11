"""
xor_stream.py - XOR Stream Cipher and Environmental Entropy Divergence Simulator.

Implements the second hypothesis from README.md:
Mapping data over a shared entropy stream using XOR (equivalent to a One-Time Pad),
and simulating environmental receiver noise / divergence to empirically test whether
two receivers can successfully decrypt transmissions without an error-free key channel.
"""

import math
import random
from typing import Dict, Optional, Tuple, Union


def compute_shannon_entropy(data: bytes) -> float:
    """
    Calculate the Shannon entropy of a byte sequence in bits per byte (0 to 8).
    """
    if not data:
        return 0.0

    counts: Dict[int, int] = {}
    for byte in data:
        counts[byte] = counts.get(byte, 0) + 1

    total = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)

    return round(entropy, 4)


def xor_bytes(data: bytes, pad: bytes) -> bytes:
    """
    Bitwise XOR two byte sequences of equal length.
    """
    if len(data) != len(pad):
        raise ValueError(f"Data length ({len(data)}) must match pad length ({len(pad)})")
    return bytes(a ^ b for a, b in zip(data, pad))


def introduce_environmental_noise(
    data: bytes,
    ber: float,
    seed: Optional[int] = None,
) -> Tuple[bytes, int]:
    """
    Simulate environmental wireless noise divergence across an entropy stream
    by randomly flipping bits with probability `ber` (Bit Error Rate).

    Returns:
        Tuple of (noisy_data, flipped_bit_count).
    """
    if ber <= 0.0:
        return data, 0
    if ber >= 1.0:
        return bytes(~b & 0xFF for b in data), len(data) * 8

    rng = random.Random(seed)
    byte_arr = bytearray(data)
    flipped_bits = 0

    for i in range(len(byte_arr)):
        byte_val = byte_arr[i]
        for bit_pos in range(8):
            if rng.random() < ber:
                byte_val ^= (1 << bit_pos)
                flipped_bits += 1
        byte_arr[i] = byte_val

    return bytes(byte_arr), flipped_bits


def calculate_hamming_distance(a: bytes, b: bytes) -> int:
    """
    Calculate total bit-level Hamming distance between two byte sequences.
    """
    if len(a) != len(b):
        raise ValueError("Byte sequences must be of equal length to compute Hamming distance")

    distance = 0
    for byte_a, byte_b in zip(a, b):
        diff = byte_a ^ byte_b
        # Count set bits in diff
        distance += bin(diff).count("1")

    return distance


def run_xor_simulation(
    message: bytes,
    entropy_pad: bytes,
    receiver_ber: float = 0.0,
    noise_seed: Optional[int] = None,
) -> Dict[str, Union[int, float, bool]]:
    """
    Simulate Alice encrypting a message with her copy of the entropy stream,
    and Bob attempting to decrypt it using his copy (subject to environmental divergence).
    """
    msg_len = len(message)
    if len(entropy_pad) < msg_len:
        raise ValueError(
            f"Entropy pad size ({len(entropy_pad)}) is smaller than message ({msg_len}). "
            "A One-Time Pad requires an entropy stream at least as long as the payload."
        )

    alice_pad = entropy_pad[:msg_len]

    # Alice transmits ciphertext C = M ^ E_alice
    ciphertext = xor_bytes(message, alice_pad)

    # Bob's receiver captures environmental entropy, potentially diverged by noise
    bob_pad, pad_bits_diverged = introduce_environmental_noise(
        alice_pad, ber=receiver_ber, seed=noise_seed
    )

    # Bob attempts decryption: M' = C ^ E_bob
    decrypted_message = xor_bytes(ciphertext, bob_pad)

    # Calculate metrics
    message_bit_errors = calculate_hamming_distance(message, decrypted_message)
    total_bits = msg_len * 8
    actual_ber = message_bit_errors / total_bits if total_bits > 0 else 0.0
    is_exact_match = (decrypted_message == message)

    return {
        "message_size": msg_len,
        "exact_match": is_exact_match,
        "message_entropy": compute_shannon_entropy(message),
        "ciphertext_entropy": compute_shannon_entropy(ciphertext),
        "pad_entropy": compute_shannon_entropy(alice_pad),
        "configured_ber": receiver_ber,
        "pad_bits_diverged": pad_bits_diverged,
        "message_bit_errors": message_bit_errors,
        "measured_ber": round(actual_ber, 6),
    }
