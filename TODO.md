# Project TODOs

## Code Cleanup & Modernization
- [ ] Rename `test file similarity2.py` to `test_file_similarity.py` (remove spaces, use snake_case).
- [ ] Update code to Python 3 syntax (fix `print` statements).
- [ ] Fix file encoding (remove non-ASCII characters like `\x96` in comments).
- [ ] Remove unused imports (`profile`, `sys`, `subprocess`) and duplicate `os` import.
- [ ] Format code according to PEP 8 standards (indentation, whitespace).

## Robustness & Portability
- [ ] Remove hardcoded absolute paths (e.g., `C:\Users\Owner\Downloads\*`). Use relative paths or configuration arguments.
- [ ] Handle missing files gracefully (e.g., check if `capture.bin` exists before opening).
- [ ] Fix potential logic errors (e.g., redundant loops in `find_longest_match_list`).

## Documentation
- [ ] Add docstrings to functions explaining their purpose and arguments.
- [ ] Add comments to clarify complex logic (e.g., Rabin-Karp implementation).

## Project Configuration
- [ ] Create a `.gitignore` file to exclude temporary files and build artifacts.
- [ ] Create a `requirements.txt` if any external dependencies are needed (currently only standard library seems to be used, but good to check).
