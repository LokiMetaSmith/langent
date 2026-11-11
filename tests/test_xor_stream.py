"""
Tests for xor_stream.py - XOR stream cipher and environmental noise modeling.
"""

import pytest
from test_file_similarity import main
from xor_stream import (
    calculate_hamming_distance,
    compute_shannon_entropy,
    introduce_environmental_noise,
    run_xor_simulation,
    xor_bytes,
)


def test_compute_shannon_entropy():
    # Empty byte sequence
    assert compute_shannon_entropy(b"") == 0.0
    # Zero entropy (identical bytes)
    assert compute_shannon_entropy(b"AAAAAAA") == 0.0
    # Maximum entropy byte distribution (all 256 byte values equally distributed)
    full_byte_range = bytes(range(256)) * 4
    ent = compute_shannon_entropy(full_byte_range)
    assert abs(ent - 8.0) < 0.001


def test_xor_bytes():
    a = b"\x0f\xf0\xaa"
    b = b"\x55\x55\x55"
    assert xor_bytes(a, b) == b"\x5a\xa5\xff"

    with pytest.raises(ValueError):
        xor_bytes(b"\x01", b"\x01\x02")


def test_hamming_distance():
    a = b"\x00\x00"
    b = b"\x01\x03"  # 1 bit in first byte, 2 bits in second byte -> 3 bits
    assert calculate_hamming_distance(a, b) == 3

    with pytest.raises(ValueError):
        calculate_hamming_distance(b"a", b"ab")


def test_introduce_environmental_noise():
    data = b"\x00" * 100
    # Zero BER
    clean, flipped = introduce_environmental_noise(data, ber=0.0)
    assert clean == data
    assert flipped == 0

    # 100% BER
    inverted, flipped = introduce_environmental_noise(data, ber=1.0)
    assert inverted == b"\xff" * 100
    assert flipped == 800

    # Intermediate BER
    noisy, flipped = introduce_environmental_noise(data, ber=0.1, seed=123)
    assert noisy != data
    assert flipped > 0


def test_xor_simulation_clean_and_noisy():
    msg = b"Confidential transmission message"
    pad = b"R" * len(msg)

    # Clean OTP transmission
    clean_res = run_xor_simulation(msg, pad, receiver_ber=0.0)
    assert clean_res["exact_match"] is True
    assert clean_res["message_bit_errors"] == 0

    # Noisy transmission (diverged entropy)
    noisy_res = run_xor_simulation(msg, pad, receiver_ber=0.05, noise_seed=42)
    assert noisy_res["exact_match"] is False
    assert noisy_res["message_bit_errors"] > 0
    assert noisy_res["pad_bits_diverged"] > 0


def test_xor_pad_too_short():
    with pytest.raises(ValueError, match="Entropy pad size"):
        run_xor_simulation(b"Long message", b"short")


def test_cli_xor_subcommand(tmp_path, capsys):
    msg_file = tmp_path / "msg.bin"
    msg_file.write_bytes(b"Testing XOR transmission via CLI")
    ret = main(["xor", "-t", str(msg_file), "-s", "777", "--ber", "0.0"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Exact Match Decrypted:True" in captured.out
