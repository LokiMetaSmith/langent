# Langent Project Roadmap & TODO

## Completed Tasks
- [x] Rename `test file similarity2.py` to `test_file_similarity.py` (adheres to PEP 8 snake_case conventions).
- [x] Modernize code to Python 3 with strict binary mode (`bytes`) support.
- [x] Replace hardcoded paths (`C:\Users\Owner\...`) with flexible `argparse` CLI subcommands (`downloads`, `file`, `rabin`).
- [x] Harden Rabin-Karp pattern matcher for arbitrary binary streams and handle edge cases (empty strings/patterns, pattern > text).
- [x] Implement comprehensive unit and integration test suite using `pytest` (46 tests across core modules).
- [x] Implement Entropy Transmission Simulation (`simulation.py`) with `simulate` CLI command to evaluate Alice/Bob transmission hypothesis.
- [x] Implement constant-memory streaming Rabin-Karp search (`stream_rabin_karp_matcher` and `--stream` flag) for large captures.
- [x] Implement standard packaging with `pyproject.toml` providing the `langent` console executable.
- [x] Add speed and collision benchmark CLI subcommand (`benchmark`).
- [x] Implement XOR Stream Cipher and Environmental Noise Divergence Simulator (`xor_stream.py` and `xor` CLI subcommand).
- [x] Implement Framed Binary Network Wire Protocol with CRC32 and Lossy Wireless Channel Simulator (`protocol.py` and `channel` CLI subcommand).
- [x] Implement Content-Defined Chunking (CDC) with Rabin Fingerprint boundaries and entropy overlap analyzer (`cdc.py` and `cdc` CLI subcommand).

## Future Roadmap & Architectural Enhancements
- [ ] Add GPU/C-extension acceleration for multi-gigabyte entropy dictionary indexing.
- [ ] Support direct SDR (Software Defined Radio) / raw I/Q capture entropy ingestion.
- [ ] Add FEC (Forward Error Correction, e.g. Reed-Solomon) packet recovery simulation for lossy channels.
