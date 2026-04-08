# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-04-08

### Fixed
- **Thread safety in watcher**: Added `threading.Lock` around the shared pending files dict.
- **N+1 query bug**: ChromaDB collection IDs are now loaded once and cached in memory during indexing.
- **Batched deletions**: File removals are now batched into single ChromaDB calls.
- **`vault_exists()` empty path**: Empty `vault_path` no longer resolves to CWD.
- **`MARKSEEK_INDEX_PATH` env var**: Now always overrides config file.
- **Symlink escape paths**: `search()` handles `ValueError` from `relative_to()`.
- **Watcher shutdown**: Added 5-second timeout to `observer.join()`.
- **Docs/README**: Fixed commands to match actual CLI (`--watch` and `--index`).

### Added
- Sentence splitting with abbreviation awareness for long paragraphs.
- 17 unit tests covering config loading, saving, and text chunking.

### Removed
- Stale `templates/*` package_data reference.
- Unused `pytest-asyncio` dev dependency.

## [0.1.0] - 2026-04-08

### Added
- Initial release.
- Semantic search over markdown/Obsidian vaults.
- Local ChromaDB index with incremental file hashing.
- Filesystem watcher for automatic reindexing.
- CLI and YAML config with env var overrides.
