"""
Tests for protocol.py - Framed binary protocol and lossy channel simulation.
"""

import pytest
from protocol import (
    LossyWirelessChannel,
    Packet,
    fragment_payload,
    reassemble_packets,
    simulate_packet_transfer,
)
from test_file_similarity import main


def test_packet_serialize_and_deserialize():
    payload = b"Hello Network Protocol Frame!"
    pkt = Packet(seq_num=7, payload=payload, is_last=True, is_token_stream=True)
    frame = pkt.serialize()

    deserialized = Packet.deserialize(frame)
    assert deserialized.seq_num == 7
    assert deserialized.payload == payload
    assert deserialized.is_last is True
    assert deserialized.is_token_stream is True


def test_packet_crc_corruption():
    pkt = Packet(seq_num=1, payload=b"Payload data")
    frame = bytearray(pkt.serialize())

    # Tamper with payload byte
    frame[12] ^= 0xFF

    with pytest.raises(ValueError, match="CRC32 mismatch"):
        Packet.deserialize(bytes(frame))


def test_packet_invalid_header():
    with pytest.raises(ValueError, match="Packet data too short"):
        Packet.deserialize(b"short")

    corrupted_magic = b"XX" + b"\x00" * 20
    with pytest.raises(ValueError, match="Invalid magic bytes"):
        Packet.deserialize(corrupted_magic)


def test_fragment_and_reassemble():
    data = b"0123456789" * 300  # 3000 bytes
    packets = fragment_payload(data, max_payload_per_packet=1000)
    assert len(packets) == 3
    assert packets[0].is_last is False
    assert packets[1].is_last is False
    assert packets[2].is_last is True

    reassembled = reassemble_packets(packets)
    assert reassembled == data


def test_reassemble_out_of_order():
    packets = [
        Packet(seq_num=1, payload=b"world"),
        Packet(seq_num=0, payload=b"hello "),
    ]
    assert reassemble_packets(packets) == b"hello world"


def test_reassemble_missing_packet():
    packets = [
        Packet(seq_num=0, payload=b"hello "),
        Packet(seq_num=2, payload=b"missing packet #1"),
    ]
    with pytest.raises(ValueError, match="Missing packet sequence"):
        reassemble_packets(packets)


def test_lossy_channel_clean_and_lossy():
    payload = b"X" * 4000
    clean_res = simulate_packet_transfer(payload, drop_rate=0.0, corruption_rate=0.0)
    assert clean_res["reconstructed_successfully"] is True
    assert clean_res["packets_dropped"] == 0

    lossy_res = simulate_packet_transfer(
        payload, drop_rate=0.5, corruption_rate=0.5, seed=123
    )
    assert lossy_res["reconstructed_successfully"] is False
    assert lossy_res["packets_dropped"] > 0 or lossy_res["crc_errors_detected"] > 0


def test_cli_channel_subcommand(tmp_path, capsys):
    target = tmp_path / "payload.bin"
    target.write_bytes(b"Data for packet framing CLI test")
    ret = main(["channel", "-t", str(target), "--drop-rate", "0.0"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Reconstructed Successfully: True" in captured.out
