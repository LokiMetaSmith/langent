"""
Tests for test_file_similarity.py - Rabin-Karp matcher and file similarity tools.
"""

import os
import pytest
from test_file_similarity import (
    rabin_karp_matcher,
    find_longest_match,
    compare_files,
    compare_downloads,
    main,
)


class TestRabinKarpMatcher:
    def test_basic_string_matching(self):
        text = "ABABDABACDABABCABAB"
        pattern = "ABABCABAB"
        matches = rabin_karp_matcher(text, pattern)
        assert matches == [10]

    def test_multiple_occurrences(self):
        text = "banana"
        pattern = "an"
        matches = rabin_karp_matcher(text, pattern)
        assert matches == [1, 3]

    def test_binary_stream_matching(self):
        text = bytes([0x00, 0x1A, 0xFF, 0xFE, 0x01, 0xFF, 0xFE, 0x22])
        pattern = bytes([0xFF, 0xFE])
        matches = rabin_karp_matcher(text, pattern)
        assert matches == [2, 5]

    def test_pattern_not_found(self):
        text = b"random_entropy_stream_xyz"
        pattern = b"not_present"
        matches = rabin_karp_matcher(text, pattern)
        assert matches == []

    def test_pattern_equal_to_text(self):
        payload = b"\xde\xad\xbe\xef"
        assert rabin_karp_matcher(payload, payload) == [0]

    def test_pattern_longer_than_text(self):
        text = b"short"
        pattern = b"longer_pattern"
        assert rabin_karp_matcher(text, pattern) == []

    def test_empty_pattern_or_text(self):
        assert rabin_karp_matcher(b"", b"abc") == []
        assert rabin_karp_matcher(b"abc", b"") == []
        assert rabin_karp_matcher(b"", b"") == []


class TestSequenceMatching:
    def test_find_longest_match(self):
        data_a = b"abcdef123456789xyz"
        data_b = b"prefix_123456789_suffix"
        a_idx, b_idx, length = find_longest_match(data_a, data_b)
        assert length == 9
        assert data_a[a_idx : a_idx + length] == b"123456789"
        assert data_b[b_idx : b_idx + length] == b"123456789"

    def test_compare_files(self, tmp_path):
        cap_file = tmp_path / "capture.bin"
        target_file = tmp_path / "target.bin"

        cap_content = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        target_content = b"\x00\x01\x02\x99\x04\x05\x06\x07"

        cap_file.write_bytes(cap_content)
        target_file.write_bytes(target_content)

        delta, opcodes = compare_files(str(cap_file), str(target_file))
        assert len(opcodes) > 0
        assert any(tag == "replace" for tag, _, _, _, _ in opcodes)

    def test_compare_downloads(self, tmp_path):
        cap_file = tmp_path / "capture.bin"
        cap_file.write_bytes(b"hello world of entropy")

        f1 = tmp_path / "file1.bin"
        f1.write_bytes(b"world of")

        f2 = tmp_path / "file2.bin"
        f2.write_bytes(b"no common parts here")

        pattern = str(tmp_path / "file*.bin")
        results = compare_downloads(str(cap_file), pattern)

        # Should match both files
        assert len(results) == 2
        f1_res = next(r for r in results if r[0] == str(f1))
        assert f1_res[3] == len(b"world of")


class TestCLI:
    def test_cli_help_or_no_args(self, capsys):
        assert main([]) == 1

    def test_cli_rabin_pattern_literal(self, tmp_path, capsys):
        cap = tmp_path / "capture.bin"
        cap.write_bytes(b"data stream with signature inside")
        ret = main(["rabin", "-c", str(cap), "-p", "signature"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Found 1 match(es): [17]" in captured.out

    def test_cli_rabin_pattern_file(self, tmp_path, capsys):
        cap = tmp_path / "capture.bin"
        cap.write_bytes(b"\xaa\xbb\xcc\xdd\xee")
        pat = tmp_path / "pat.bin"
        pat.write_bytes(b"\xcc\xdd")

        ret = main(["rabin", "-c", str(cap), "-f", str(pat)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Found 1 match(es): [2]" in captured.out

    def test_cli_file_comparison(self, tmp_path, capsys):
        cap = tmp_path / "capture.bin"
        target = tmp_path / "target.bin"
        cap.write_bytes(b"ABCDEF")
        target.write_bytes(b"ABXDEF")

        ret = main(["file", "-c", str(cap), "-t", str(target)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Opcodes count:" in captured.out

    def test_cli_downloads(self, tmp_path, capsys):
        cap = tmp_path / "capture.bin"
        target = tmp_path / "sub_target.bin"
        cap.write_bytes(b"testing 123")
        target.write_bytes(b"123")

        ret = main(["downloads", "-c", str(cap), "-p", str(tmp_path / "*.bin")])
        assert ret == 0
        captured = capsys.readouterr()
        assert "longest match at capture offset" in captured.out

    def test_cli_missing_file_error(self, capsys):
        ret = main(["rabin", "-c", "non_existent_file.bin", "-p", "foo"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "Error running Rabin-Karp matcher" in captured.err
