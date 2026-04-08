![markseek](https://img.shields.io/badge/markseek-semantic--search-blue?style=flat-square)
![MIT License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-orange?style=flat-square)

# markseek

Semantic search over your markdown vault. Built on Obsidian. Lightweight, local, zero-config.

Query by meaning, not keywords. Works offline. No API keys.

## Why

You want semantic search over your Obsidian vault, your notes, or any folder of
markdown files. Everything else that does this is either a heavy web app
(PrivateGPT, AnythingLLM — full Docker containers, web UIs, hundreds of MB of
RAM) or only works while the desktop app is open.

markseek is one package, no web server, no Docker, no cloud:

```
$ markseek "what did Frankl say about the bird"

Search results for: "what did Frankl say about the bird"

─── Result 1 (relevance: 0.91) ───
File: letters/Pen Pal.md
Snippet:
And then a bird lands on the dirt he just dug up and looks at him.
That's it. That's the whole philosophy. A man who has lost literally
everything and a bird lands and looks at him and the world is still,
for one second, looking back.
```

## Install

```bash
pip install markseek
```

## Quick Start

1. **Configure your vault:**
```bash
markseek --configure
```

Or point it directly via environment variable:
```bash
export MARKSEEK_VAULT_PATH="~/Documents/Obsidian Vault"
```

2. **Search:**
```bash
markseek "what does Frankl say about meaning and suffering" -n 5
```

3. **Watch for changes (background index):**
```bash
markseek --watch
```

Run this in a terminal, or as a systemd/launchd service. Whenever you
modify a `.md` file in the vault, it gets re-indexed automatically
within 2 seconds.

## Commands

| Command | Description |
|---------|-------------|
| `markseek "your query"` | Semantic search (auto-indexes on first run) |
| `markseek -n 10 "query"` | Top 10 results |
| `markseek --watch` | Start auto-indexing watcher (background) |
| `markseek --index` | Manually update the index |
| `markseek --index --rebuild` | Force full reindex |
| `markseek --status` | Show index stats (files, chunks, model) |
| `markseek --configure` | Interactive config wizard |

## How It Works

1. **Markdown files** in your vault are chunked by paragraphs (~500 chars).
2. **Local embeddings** -- `all-MiniLM-L6-v2` (~80MB, CPU, no GPU needed) converts each chunk to a vector.
3. **ChromaDB** stores the vectors locally for fast similarity search.
4. **Auto-indexing** -- a file watcher detects changes and re-indexes only the changed file.
5. **Semantic queries** -- your question gets embedded and matched against all chunks, ranked by cosine similarity.

No files are uploaded anywhere. Everything runs on your machine.

## Configuration

Config file: `~/.config/markseek/config.yaml`

```yaml
vault_path: ~/Documents/Obsidian Vault
index_path: ~/.cache/markseek/index
model_name: all-MiniLM-L6-v2
max_chunk_size: 500
debounce_seconds: 2.0
log_level: INFO
extensions: [".md"]
```

Environment variables take priority:
- `MARKSEEK_VAULT_PATH` -- override vault path
- `MARKSEEK_INDEX_PATH` -- override index location

## As a Library

```python
from markseek.config import Config
from markseek.core import Index

cfg = Config.load()
index = Index(cfg)
results = index.search("meaning through encountering someone")
```

## License

MIT. See [LICENSE](LICENSE).
