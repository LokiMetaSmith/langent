"""
Unit and integration tests for simulation.py and new streaming/benchmark capabilities.
"""

import io
import pytest
from simulation import (
    EntropyStream,
    Token,
    build_entropy_index,
    decode_transmission,
    encode_transmission,
    generate_prng_entropy,
    run_simulation,
)
from test_file_similarity import main, stream_rabin_karp_matcher


class TestSimulation:
    def test_prng_entropy_deterministic(self):
        e1 = generate_prng_entropy(1234, 100)
        e2 = generate_prng_entropy(1234, 100)
        e3 = generate_prng_entropy(5678, 100)
        assert e1 == e2
        assert len(e1) == 100
        assert e1 != e3

    def test_entropy_stream_from_file(self, tmp_path):
        f = tmp_path / "entropy.bin"
        f.write_bytes(b"0123456789ABCDEF")
        stream = EntropyStream.from_file(str(f))
        assert stream.size == 16
        assert stream.slice(10, 6) == b"ABCDEF"

        with pytest.raises(IndexError):
            stream.slice(10, 10)

    def test_token_serialization(self):
        # Test pointer token
        ptr = Token(Token.TAG_POINTER, offset=42000, length=250)
        packed_ptr = ptr.pack()
        unpacked_ptr = Token.unpack_from(io.BytesIO(packed_ptr))
        assert unpacked_ptr is not None
        assert unpacked_ptr.tag == Token.TAG_POINTER
        assert unpacked_ptr.offset == 42000
        assert unpacked_ptr.length == 250
        assert ptr.wire_size() == 7

        # Test literal token
        lit = Token(Token.TAG_LITERAL, literal_bytes=b"hello_entropy")
        packed_lit = lit.pack()
        unpacked_lit = Token.unpack_from(io.BytesIO(packed_lit))
        assert unpacked_lit is not None
        assert unpacked_lit.tag == Token.TAG_LITERAL
        assert unpacked_lit.literal_bytes == b"hello_entropy"
        assert lit.wire_size() == 3 + len(b"hello_entropy")

    def test_roundtrip_encode_decode(self):
        entropy = EntropyStream.from_seed(999, 50000)
        # Create composite payload: literal prefix + slice from entropy + literal suffix
        match_slice = entropy.slice(1200, 24)
        payload = b"HEADER_" + match_slice + b"_FOOTER"

        tokens = encode_transmission(payload, entropy, min_match_len=8)
        reconstructed = decode_transmission(tokens, entropy)
        assert reconstructed == payload

        metrics = run_simulation(payload, entropy, min_match_len=8)
        assert metrics["verified"] is True
        assert metrics["pointer_tokens_count"] >= 1
        assert metrics["literal_tokens_count"] >= 1

    def test_simulation_with_no_matches(self):
        entropy = EntropyStream(b"ABCDEFGH")
        payload = b"12345678"
        metrics = run_simulation(payload, entropy, min_match_len=4)
        assert metrics["verified"] is True
        assert metrics["pointer_tokens_count"] == 0
        assert metrics["literal_tokens_count"] == 1


class TestStreamingRabinKarp:
    def test_streaming_matches_in_memory(self):
        data = b"0123456789" * 50 + b"MATCH_HERE" + b"0123456789" * 20 + b"MATCH_HERE"
        pattern = b"MATCH_HERE"
        matches = list(stream_rabin_karp_matcher(io.BytesIO(data), pattern, chunk_size=16))
        assert len(matches) == 2
        assert data[matches[0] : matches[0] + len(pattern)] == pattern
        assert data[matches[1] : matches[1] + len(pattern)] == pattern

    def test_streaming_empty_or_short(self):
        assert list(stream_rabin_karp_matcher(io.BytesIO(b""), b"abc")) == []
        assert list(stream_rabin_karp_matcher(io.BytesIO(b"ab"), b"abc")) == []
        assert list(stream_rabin_karp_matcher(io.BytesIO(b"abc"), b"")) == []


class TestExtendedCLI:
    def test_cli_streaming_rabin(self, tmp_path, capsys):
        cap = tmp_path / "large_cap.bin"
        cap.write_bytes(b"start" + b"target_marker" * 3 + b"end")
        ret = main(["rabin", "-c", str(cap), "-p", "target_marker", "--stream"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Found 3 match(es): [5, 18, 31]" in captured.out

    def test_cli_simulate_subcommand(self, tmp_path, capsys):
        target = tmp_path / "payload.bin"
        target.write_bytes(b"test transmission payload for simulation")
        ret = main(["simulate", "-t", str(target), "-s", "42", "--entropy-size", "10000"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "=== Transmission Simulation Report ===" in captured.out
        assert "Round-trip Verified:   True" in captured.out

    def test_cli_benchmark_subcommand(self, capsys):
        ret = main(["benchmark", "--size", "10000", "--pattern-len", "8"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Benchmarking Rabin-Karp pattern search" in captured.out
