#!/usr/bin/env python3
"""
test_file_similarity.py - File similarity, transmission simulation, and entropy CLI toolkit.

Provides:
- Rabin-Karp pattern searching (in-memory and chunked streaming)
- SequenceMatcher comparison
- Entropy transmission simulation (Alice/Bob model)
- XOR stream cipher and environmental noise modeling
- Framed binary packet protocol and lossy channel simulation
- Content-Defined Chunking (CDC) dictionary matching
- Performance benchmarking
"""

import argparse
import difflib
import glob
import os
import sys
import time
from typing import BinaryIO, Generator, List, Optional, Sequence, Tuple, Union

from cdc import chunk_data, evaluate_chunk_overlap
from protocol import simulate_packet_transfer
from simulation import (
    EntropyStream,
    decode_transmission,
    encode_transmission,
    run_simulation,
)
from xor_stream import run_xor_simulation


def rabin_karp_matcher(
    text: Union[str, bytes],
    pattern: Union[str, bytes],
    d: int = 256,
    q: int = 2147483647,
) -> List[int]:
    """
    Search for occurrences of pattern in text using the Rabin-Karp algorithm.
    """
    if isinstance(text, str):
        text_bytes = [ord(c) for c in text]
    else:
        text_bytes = list(text)

    if isinstance(pattern, str):
        pattern_bytes = [ord(c) for c in pattern]
    else:
        pattern_bytes = list(pattern)

    n = len(text_bytes)
    m = len(pattern_bytes)

    if m == 0 or n == 0 or m > n:
        return []

    h = pow(d, m - 1, q)
    p = 0
    t = 0
    result: List[int] = []

    # Preprocessing / initial hash calculation
    for i in range(m):
        p = (d * p + pattern_bytes[i]) % q
        t = (d * t + text_bytes[i]) % q

    # Slide window over text
    for s in range(n - m + 1):
        if p == t:
            if pattern_bytes == text_bytes[s : s + m]:
                result.append(s)
        if s < n - m:
            t = (t - h * text_bytes[s]) % q
            t = (t * d + text_bytes[s + m]) % q
            t = (t + q) % q

    return result


def stream_rabin_karp_matcher(
    stream: BinaryIO,
    pattern: bytes,
    chunk_size: int = 65536,
    d: int = 256,
    q: int = 2147483647,
) -> Generator[int, None, None]:
    """
    Stream-based Rabin-Karp matcher for large files without loading entire file into memory.
    """
    m = len(pattern)
    if m == 0:
        return

    pattern_bytes = list(pattern)
    h = pow(d, m - 1, q)
    p = 0
    for i in range(m):
        p = (d * p + pattern_bytes[i]) % q

    window = bytearray(stream.read(m))
    if len(window) < m:
        return

    t = 0
    for b in window:
        t = (d * t + b) % q

    offset = 0
    if p == t and list(window) == pattern_bytes:
        yield offset

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break

        for byte_val in chunk:
            first_byte = window.pop(0)
            window.append(byte_val)
            offset += 1

            t = (t - h * first_byte) % q
            t = (t * d + byte_val) % q
            t = (t + q) % q

            if p == t and list(window) == pattern_bytes:
                yield offset


def find_longest_match(
    data_a: bytes, data_b: bytes
) -> Tuple[int, int, int]:
    """Find the longest common subsequence match between two binary sequences."""
    matcher = difflib.SequenceMatcher(None, data_a, data_b)
    match = matcher.find_longest_match(0, len(data_a), 0, len(data_b))
    return (match.a, match.b, match.size)


def compare_files(
    capture_path: str, target_path: str
) -> Tuple[int, List[Tuple[str, int, int, int, int]]]:
    """Compare a capture file against a target file using SequenceMatcher."""
    with open(capture_path, "rb") as fa:
        data_a = fa.read()
    with open(target_path, "rb") as fb:
        data_b = fb.read()

    matcher = difflib.SequenceMatcher(None, data_a, data_b)
    opcodes = matcher.get_opcodes()

    total_delta = 0
    for tag, alo, ahi, blo, bhi in opcodes:
        total_delta += (bhi - blo) - 5

    return total_delta, opcodes


def compare_downloads(capture_path: str, glob_pattern: str) -> List[Tuple[str, int, int, int]]:
    """Compare a capture file against all files matching a glob pattern."""
    if not os.path.exists(capture_path):
        raise FileNotFoundError(f"Capture file not found: {capture_path}")

    with open(capture_path, "rb") as fa:
        data_a = fa.read()

    results = []
    for infile in glob.iglob(glob_pattern):
        if os.path.isfile(infile):
            with open(infile, "rb") as fb:
                data_b = fb.read()
            a_idx, b_idx, size = find_longest_match(data_a, data_b)
            results.append((infile, a_idx, b_idx, size))
            print(f"{infile}: longest match at capture offset {a_idx}, target offset {b_idx}, length {size}")
    return results


def run_benchmark(size: int = 1_000_000, pattern_len: int = 16) -> int:
    """Run benchmark comparing Rabin-Karp against built-in search on random bytes."""
    import random

    print(f"Generating {size:,} bytes of synthetic entropy stream...")
    rng = random.Random(1337)
    data = rng.randbytes(size) if hasattr(rng, "randbytes") else rng.getrandbits(size * 8).to_bytes(size, "big")

    target_offset = size // 2
    pattern = rng.randbytes(pattern_len) if hasattr(rng, "randbytes") else rng.getrandbits(pattern_len * 8).to_bytes(pattern_len, "big")
    data = data[:target_offset] + pattern + data[target_offset + pattern_len :]

    print(f"Benchmarking Rabin-Karp pattern search (pattern length: {pattern_len} bytes)...")
    t0 = time.perf_counter()
    matches = rabin_karp_matcher(data, pattern)
    elapsed_rk = time.perf_counter() - t0
    speed_rk = (size / (1024 * 1024)) / elapsed_rk if elapsed_rk > 0 else 0

    print(f"Rabin-Karp found match at: {matches} in {elapsed_rk:.4f}s ({speed_rk:.2f} MB/s)")

    print("Benchmarking Python built-in bytes.find()...")
    t1 = time.perf_counter()
    builtin_match = data.find(pattern)
    elapsed_builtin = time.perf_counter() - t1
    speed_builtin = (size / (1024 * 1024)) / elapsed_builtin if elapsed_builtin > 0 else 0

    print(f"Built-in find at: {builtin_match} in {elapsed_builtin:.4f}s ({speed_builtin:.2f} MB/s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="langent",
        description="Langent - Wireless language out of entropy toolkit.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # downloads subcommand
    downloads_parser = subparsers.add_parser(
        "downloads", help="Compare a capture file against a pattern of files."
    )
    downloads_parser.add_argument(
        "--capture", "-c", required=True, help="Path to capture reference file"
    )
    downloads_parser.add_argument(
        "--pattern", "-p", required=True, help="Glob pattern for target files to compare"
    )

    # file subcommand
    file_parser = subparsers.add_parser(
        "file", help="Compare a single file against a capture reference file."
    )
    file_parser.add_argument(
        "--capture", "-c", required=True, help="Path to capture reference file"
    )
    file_parser.add_argument(
        "--target", "-t", required=True, help="Path to target file"
    )

    # rabin subcommand
    rabin_parser = subparsers.add_parser(
        "rabin", help="Search for a pattern or file in capture data using Rabin-Karp."
    )
    rabin_parser.add_argument(
        "--capture", "-c", required=True, help="Path to capture reference file"
    )
    group = rabin_parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--pattern", "-p", help="Literal text/bytes pattern to search for"
    )
    group.add_argument(
        "--pattern-file", "-f", help="Path to pattern file to search for"
    )
    rabin_parser.add_argument(
        "-d", "--radix", type=int, default=256, help="Radix/alphabet size (default: 256)"
    )
    rabin_parser.add_argument(
        "-q", "--modulus", type=int, default=2147483647, help="Modulus prime (default: 2147483647)"
    )
    rabin_parser.add_argument(
        "--stream", action="store_true", help="Process capture in streaming mode chunk by chunk"
    )

    # simulate subcommand
    simulate_parser = subparsers.add_parser(
        "simulate", help="Simulate entropy transmission between Alice and Bob."
    )
    simulate_parser.add_argument(
        "--target", "-t", required=True, help="Payload file to transmit"
    )
    entropy_group = simulate_parser.add_mutually_exclusive_group(required=True)
    entropy_group.add_argument(
        "--seed", "-s", type=int, help="PRNG integer seed for shared entropy"
    )
    entropy_group.add_argument(
        "--entropy-file", "-e", help="Path to shared entropy reference file"
    )
    simulate_parser.add_argument(
        "--entropy-size", type=int, default=1_000_000, help="Size of PRNG entropy stream (default: 1,000,000)"
    )
    simulate_parser.add_argument(
        "--min-match", type=int, default=8, help="Minimum match length in bytes (default: 8)"
    )

    # xor subcommand
    xor_parser = subparsers.add_parser(
        "xor", help="Simulate XOR stream cipher and environmental noise divergence."
    )
    xor_parser.add_argument(
        "--target", "-t", required=True, help="Message file to encrypt/transmit"
    )
    xor_entropy_group = xor_parser.add_mutually_exclusive_group(required=True)
    xor_entropy_group.add_argument(
        "--seed", "-s", type=int, help="PRNG integer seed for shared entropy pad"
    )
    xor_entropy_group.add_argument(
        "--entropy-file", "-e", help="Path to shared entropy pad file"
    )
    xor_parser.add_argument(
        "--ber", type=float, default=0.0, help="Simulated receiver bit error rate (default: 0.0)"
    )
    xor_parser.add_argument(
        "--noise-seed", type=int, default=None, help="PRNG seed for reproducible noise generation"
    )

    # channel subcommand
    channel_parser = subparsers.add_parser(
        "channel", help="Simulate packetized transmission over lossy wireless channel."
    )
    channel_parser.add_argument(
        "--target", "-t", required=True, help="Payload file to packetize and transmit"
    )
    channel_parser.add_argument(
        "--drop-rate", type=float, default=0.0, help="Packet drop rate between 0.0 and 1.0 (default: 0.0)"
    )
    channel_parser.add_argument(
        "--corruption-rate", type=float, default=0.0, help="Packet corruption rate (default: 0.0)"
    )
    channel_parser.add_argument(
        "--packet-size", type=int, default=1400, help="Maximum payload per packet (default: 1400)"
    )
    channel_parser.add_argument(
        "--seed", type=int, default=None, help="PRNG seed for channel noise"
    )

    # cdc subcommand
    cdc_parser = subparsers.add_parser(
        "cdc", help="Content-Defined Chunking and entropy dictionary matching."
    )
    cdc_parser.add_argument(
        "--target", "-t", required=True, help="Payload file to chunk"
    )
    cdc_parser.add_argument(
        "--entropy-file", "-e", help="Optional entropy file to measure chunk overlap against"
    )
    cdc_parser.add_argument(
        "--min-size", type=int, default=64, help="Minimum chunk size (default: 64)"
    )
    cdc_parser.add_argument(
        "--avg-size", type=int, default=256, help="Average chunk size (default: 256)"
    )
    cdc_parser.add_argument(
        "--max-size", type=int, default=1024, help="Maximum chunk size (default: 1024)"
    )

    # benchmark subcommand
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Run speed and collision benchmarks for Rabin-Karp matcher."
    )
    benchmark_parser.add_argument(
        "--size", type=int, default=1_000_000, help="Synthetic entropy size in bytes (default: 1,000,000)"
    )
    benchmark_parser.add_argument(
        "--pattern-len", type=int, default=16, help="Search pattern length in bytes (default: 16)"
    )

    return parser


def main(args: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if not parsed_args.command:
        parser.print_help()
        return 1

    if parsed_args.command == "downloads":
        try:
            compare_downloads(parsed_args.capture, parsed_args.pattern)
            return 0
        except Exception as e:
            print(f"Error comparing downloads: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "file":
        try:
            total_delta, opcodes = compare_files(parsed_args.capture, parsed_args.target)
            print(f"Opcodes count: {len(opcodes)}")
            print(f"Total delta metric: {total_delta}")
            for tag, alo, ahi, blo, bhi in opcodes:
                print(f"  {tag:7s} a[{alo}:{ahi}] b[{blo}:{bhi}] delta={(bhi - blo)}")
            return 0
        except Exception as e:
            print(f"Error comparing files: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "rabin":
        try:
            if parsed_args.pattern is not None:
                pattern_data = parsed_args.pattern.encode("utf-8")
            else:
                with open(parsed_args.pattern_file, "rb") as fp:
                    pattern_data = fp.read()

            if parsed_args.stream:
                with open(parsed_args.capture, "rb") as fc:
                    matches = list(
                        stream_rabin_karp_matcher(
                            fc,
                            pattern_data,
                            d=parsed_args.radix,
                            q=parsed_args.modulus,
                        )
                    )
            else:
                with open(parsed_args.capture, "rb") as fc:
                    capture_data = fc.read()
                matches = rabin_karp_matcher(
                    capture_data,
                    pattern_data,
                    d=parsed_args.radix,
                    q=parsed_args.modulus,
                )

            print(f"Found {len(matches)} match(es): {matches}")
            return 0
        except Exception as e:
            print(f"Error running Rabin-Karp matcher: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "simulate":
        try:
            with open(parsed_args.target, "rb") as ft:
                payload = ft.read()

            if parsed_args.seed is not None:
                entropy = EntropyStream.from_seed(parsed_args.seed, parsed_args.entropy_size)
            else:
                entropy = EntropyStream.from_file(parsed_args.entropy_file)

            metrics = run_simulation(payload, entropy, min_match_len=parsed_args.min_match)

            print("=== Transmission Simulation Report ===")
            print(f"Original Payload Size: {metrics['raw_size']:,} bytes")
            print(f"Shared Entropy Pool:   {metrics['entropy_pool_size']:,} bytes")
            print(f"Transmitted Wire Size: {metrics['wire_size']:,} bytes")
            print(f"Compression Ratio:     {metrics['compression_ratio']} (Wire / Original)")
            print(f"Pointer Tokens:        {metrics['pointer_tokens_count']} ({metrics['pointer_covered_bytes']} bytes covered)")
            print(f"Literal Tokens:        {metrics['literal_tokens_count']} ({metrics['literal_covered_bytes']} bytes covered)")
            print(f"Round-trip Verified:   {metrics['verified']}")
            print(f"Encode Time:           {metrics['encode_time_sec']}s")
            print(f"Decode Time:           {metrics['decode_time_sec']}s")
            return 0 if metrics["verified"] else 2
        except Exception as e:
            print(f"Error executing simulation: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "xor":
        try:
            with open(parsed_args.target, "rb") as ft:
                msg = ft.read()

            if parsed_args.seed is not None:
                entropy = EntropyStream.from_seed(parsed_args.seed, len(msg)).data
            else:
                with open(parsed_args.entropy_file, "rb") as fe:
                    entropy = fe.read()

            res = run_xor_simulation(
                msg,
                entropy,
                receiver_ber=parsed_args.ber,
                noise_seed=parsed_args.noise_seed,
            )

            print("=== XOR Stream & Noise Divergence Report ===")
            print(f"Message Size:         {res['message_size']:,} bytes")
            print(f"Message Entropy:      {res['message_entropy']} bits/byte")
            print(f"Ciphertext Entropy:   {res['ciphertext_entropy']} bits/byte")
            print(f"Pad Entropy:          {res['pad_entropy']} bits/byte")
            print(f"Configured BER:       {res['configured_ber']}")
            print(f"Pad Bits Diverged:    {res['pad_bits_diverged']}")
            print(f"Message Bit Errors:   {res['message_bit_errors']}")
            print(f"Measured BER:         {res['measured_ber']}")
            print(f"Exact Match Decrypted:{res['exact_match']}")
            return 0
        except Exception as e:
            print(f"Error executing XOR simulation: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "channel":
        try:
            with open(parsed_args.target, "rb") as ft:
                payload = ft.read()

            res = simulate_packet_transfer(
                payload,
                drop_rate=parsed_args.drop_rate,
                corruption_rate=parsed_args.corruption_rate,
                max_packet_size=parsed_args.packet_size,
                seed=parsed_args.seed,
            )

            print("=== Lossy Wireless Channel Simulation Report ===")
            print(f"Payload Size:           {res['payload_bytes']:,} bytes")
            print(f"Total Packets:          {res['total_packets']}")
            print(f"Packets Dropped:        {res['packets_dropped']}")
            print(f"Packets Corrupted:      {res['packets_corrupted']}")
            print(f"CRC32 Errors Detected:  {res['crc_errors_detected']}")
            print(f"Valid Packets Received: {res['valid_packets_received']}")
            print(f"Reconstructed Successfully: {res['reconstructed_successfully']}")
            return 0
        except Exception as e:
            print(f"Error executing channel simulation: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "cdc":
        try:
            with open(parsed_args.target, "rb") as ft:
                payload = ft.read()

            if parsed_args.entropy_file:
                with open(parsed_args.entropy_file, "rb") as fe:
                    entropy = fe.read()
                res = evaluate_chunk_overlap(
                    payload,
                    entropy,
                    min_size=parsed_args.min_size,
                    avg_size=parsed_args.avg_size,
                    max_size=parsed_args.max_size,
                )
                print("=== CDC Chunk Overlap Report ===")
                print(f"Payload Size:       {res['payload_bytes']:,} bytes")
                print(f"Payload Chunks:     {res['payload_chunks']}")
                print(f"Entropy Chunks:     {res['entropy_chunks']}")
                print(f"Matched Chunks:     {res['matched_chunks']}")
                print(f"Matched Bytes:      {res['matched_bytes']:,} bytes")
                print(f"Chunk Hit Ratio:    {res['chunk_hit_ratio']}")
                print(f"Byte Hit Ratio:     {res['byte_hit_ratio']}")
            else:
                chunks = chunk_data(
                    payload,
                    min_size=parsed_args.min_size,
                    avg_size=parsed_args.avg_size,
                    max_size=parsed_args.max_size,
                )
                print(f"Generated {len(chunks)} content-defined chunks from {len(payload):,} bytes.")
                for i, c in enumerate(chunks[:10]):
                    print(f"  Chunk {i}: offset={c.offset}, len={c.length}, digest={c.digest[:12]}...")
                if len(chunks) > 10:
                    print(f"  ... and {len(chunks) - 10} more chunks.")
            return 0
        except Exception as e:
            print(f"Error executing CDC: {e}", file=sys.stderr)
            return 1

    elif parsed_args.command == "benchmark":
        try:
            return run_benchmark(size=parsed_args.size, pattern_len=parsed_args.pattern_len)
        except Exception as e:
            print(f"Error executing benchmark: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
