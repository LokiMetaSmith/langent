"""
Tests for cdc.py - Content-Defined Chunking and entropy overlap analysis.
"""

import pytest
from cdc import Chunk, chunk_data, evaluate_chunk_overlap
from test_file_similarity import main


def test_chunk_data_empty():
    assert chunk_data(b"") == []


def test_chunk_data_small():
    data = b"small_payload"
    chunks = chunk_data(data, min_size=64, avg_size=128, max_size=256)
    assert len(chunks) == 1
    assert chunks[0].data == data
    assert chunks[0].offset == 0
    assert chunks[0].length == len(data)


def test_chunk_data_reconstruction():
    # Deterministic patterned byte stream
    data = b"BLOCK_A_12345678" * 50 + b"BLOCK_B_87654321" * 50
    chunks = chunk_data(data, min_size=32, avg_size=128, max_size=512)
    assert len(chunks) > 1

    # Verify each chunk boundary meets constraints
    for c in chunks:
        assert c.length <= 512

    # Verify perfect reconstruction
    reconstructed = b"".join(c.data for c in chunks)
    assert reconstructed == data


def test_evaluate_chunk_overlap():
    base = b"COMMON_CHUNK_PAYLOAD_TEST_" * 30
    payload = base + b"UNIQUE_PAYLOAD_SECTION_" * 10
    entropy = b"PREFIX_ENTROPY_" * 5 + base + b"SUFFIX_ENTROPY_" * 5

    res = evaluate_chunk_overlap(payload, entropy, min_size=32, avg_size=128, max_size=512)
    assert res["matched_chunks"] > 0
    assert res["matched_bytes"] > 0
    assert res["chunk_hit_ratio"] > 0.0


def test_cli_cdc_subcommand(tmp_path, capsys):
    target = tmp_path / "payload.bin"
    target.write_bytes(b"A" * 1000 + b"B" * 1000)

    # Simple chunking listing
    ret = main(["cdc", "-t", str(target), "--min-size", "64", "--max-size", "256"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Generated" in captured.out
    assert "content-defined chunks" in captured.out

    # Chunking overlap comparison
    entropy = tmp_path / "entropy.bin"
    entropy.write_bytes(b"A" * 1000 + b"C" * 1000)
    ret2 = main(["cdc", "-t", str(target), "-e", str(entropy), "--min-size", "64", "--max-size", "256"])
    assert ret2 == 0
    captured2 = capsys.readouterr()
    assert "=== CDC Chunk Overlap Report ===" in captured2.out
    assert "Matched Chunks:" in captured2.out
