"""
markseek.core -- Semantic indexing and search for markdown files.

Chunks markdown files by paragraphs, embeds them with a local model,
and stores vectors in ChromaDB. Supports incremental updates.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import chromadb

logger = logging.getLogger(__name__)


def _quiet_logs():
    """Suppress noisy library log output during embedding/search."""
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning)
    for name in ["sentence_transformers", "torch", "huggingface_hub"]:
        logging.getLogger(name).setLevel(logging.ERROR)

from markseek.config import Config


# Long-paragraph threshold: paragraphs exceeding max_chunk_size * this
# factor get split into sentences instead of kept whole.
_PARAGRAPH_OVERFLOW_FACTOR = 2


def _file_hash(filepath: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


def _discover_files(cfg: Config) -> list[Path]:
    """Find all files matching configured extensions in the vault."""
    vault = Path(cfg.vault_path)
    files = []
    for ext in cfg.extensions:
        files.extend(vault.rglob(f"*{ext}"))
    # De-duplicate and sort
    return sorted(set(files))


def _chunk_text(text: str, filepath: str, cfg: Config) -> list[dict]:
    """Split markdown text into chunks of roughly max_chunk_size characters.

    Splits on paragraph boundaries when possible. Falls back to
    sentence splitting for very long paragraphs.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current = []
    current_len = 0

    overflow_threshold = cfg.max_chunk_size * _PARAGRAPH_OVERFLOW_FACTOR

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        # If a single paragraph is much longer than max_chunk_size,
        # split it into sentences
        if len(p) > overflow_threshold:
            if current:
                chunks.append({
                    "text": "\n\n".join(current),
                    "file": filepath,
                })
                current = []
                current_len = 0

            sentences = _split_sentences(p)
            sent_chunk = []
            sent_len = 0
            for s in sentences:
                if sent_len + len(s) > cfg.max_chunk_size and sent_chunk:
                    chunks.append({
                        "text": " ".join(sent_chunk),
                        "file": filepath,
                    })
                    sent_chunk = []
                    sent_len = 0
                sent_chunk.append(s)
                sent_len += len(s)
            if sent_chunk:
                chunks.append({
                    "text": " ".join(sent_chunk),
                    "file": filepath,
                })
            continue

        if current_len + len(p) > cfg.max_chunk_size and current:
            chunks.append({
                "text": "\n\n".join(current),
                "file": filepath,
            })
            current = []
            current_len = 0
        current.append(p)
        current_len += len(p)

    if current:
        chunks.append({
            "text": "\n\n".join(current),
            "file": filepath,
        })

    return chunks


def _split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences with basic abbreviation awareness."""
    import re
    # Split on sentence-ending punctuation followed by space (or end of string)
    # Skip common abbreviations
    pattern = r'(?<=[.!?])\s+(?![A-Z][a-z]\.\s|[A-Z]\.\s|e\.g\.\s|i\.e\.\s|Dr\.\s|Mr\.\s|Mrs\.\s|Ms\.\s|Prof\.\s|Inc\.\s|Ltd\.\s|Jr\.\s|Sr\.\s|vs\.\s|etc\.\s|http|ftp)'
    return re.split(pattern, paragraph) if re.search(pattern, paragraph) else [paragraph]


class Index:
    """Manages the ChromaDB vector index for a vault."""

    COL_NAME = "markseek"

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._client: Optional[chromadb.PersistentClient] = None
        self._col = None
        self._all_ids: Optional[set[str]] = None

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            Path(self.cfg.index_path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.cfg.index_path)
        return self._client

    @property
    def collection(self):
        if self._col is None:
            self._col = self.client.get_or_create_collection(
                name=self.COL_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._col

    def _refresh_ids(self):
        """Load all chunk IDs into memory once per indexing session."""
        self._all_ids = set(self.collection.get(include=[])["ids"])

    @property
    def _existing_ids(self) -> set[str]:
        if self._all_ids is None:
            self._refresh_ids()
        return self._all_ids

    def _meta_path(self) -> Path:
        return Path(self.cfg.index_path) / "meta.json"

    def _load_meta(self) -> dict:
        p = self._meta_path()
        if p.exists():
            with open(p) as f:
                return json.load(f)
        return {"file_hashes": {}}

    def _save_meta(self, meta: dict):
        p = self._meta_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(meta, f, indent=2)

    def status(self) -> dict:
        """Return index statistics."""
        col = self.collection
        meta = self._load_meta()
        return {
            "total_chunks": col.count(),
            "indexed_files": len(meta.get("file_hashes", {})),
            "vault_path": self.cfg.vault_path,
            "index_path": self.cfg.index_path,
            "model": self.cfg.model_name,
        }

    def rebuild(self):
        """Force full reindex of all files."""
        try:
            self.client.delete_collection(self.COL_NAME)
        except ValueError:
            pass  # collection doesn't exist yet
        self._col = None
        self._all_ids = None
        meta = {"file_hashes": {}}
        self._save_meta(meta)
        self.index_all()

    def index_all(self):
        """Index all files that have changed since last index."""
        files = _discover_files(self.cfg)
        if not files:
            logger.warning("No markdown files found in vault: %s", self.cfg.vault_path)
            return

        meta = self._load_meta()
        col = self.collection

        # Load all IDs once
        self._refresh_ids()

        # Determine which files changed
        current = {}
        for f in files:
            fstr = str(f)
            h = _file_hash(f)
            if h:
                current[fstr] = h

        current_set = set(current.keys())

        # Collect all deleted file IDs and batch delete
        to_delete = []
        for eid in list(self._existing_ids):
            eid_file = eid.rsplit("::", 1)[0]
            if eid_file not in current_set:
                to_delete.append(eid)
                # Also remove from our in-memory set
                self._all_ids.discard(eid)
        if to_delete:
            col.delete(ids=to_delete)

        # Index changed/new files
        from markseek.embedder import get_model
        model = get_model(self.cfg.model_name)

        indexed_count = 0
        for fpath in files:
            fstr = str(fpath)
            old_hash = meta.get("file_hashes", {}).get(fstr)
            new_hash = current.get(fstr)

            if old_hash == new_hash:
                # Check chunks exist using cached IDs
                prefix = fstr + "::"
                matching = [eid for eid in self._existing_ids if eid.startswith(prefix)]
                if matching:
                    continue

            try:
                text = fpath.read_text()
            except Exception as e:
                logger.warning("Cannot read %s: %s", fpath.name, e)
                continue

            chunks = _chunk_text(text, fstr, self.cfg)
            if not chunks:
                continue

            texts = [chk["text"] for chk in chunks]
            ids = [f"{chk['file']}::{i}" for i, chk in enumerate(chunks)]
            metadatas = [{"file": chk["file"]} for chk in chunks]

            # Remove old chunks for this file (batch delete)
            prefix = fstr + "::"
            old_ids = [eid for eid in self._existing_ids if eid.startswith(prefix)]
            if old_ids:
                col.delete(ids=old_ids)
                for oid in old_ids:
                    self._all_ids.discard(oid)

            _quiet_logs()
            embeddings = model.encode(texts, show_progress_bar=False).tolist()

            col.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
            self._existing_ids.update(ids)
            meta.setdefault("file_hashes", {})[fstr] = new_hash
            indexed_count += 1

        self._save_meta(meta)
        if indexed_count > 0:
            logger.info("Re-indexed %d of %d files", indexed_count, len(files))
        else:
            logger.info("All %d files already up to date", len(files))

    def index_file(self, filepath: str):
        """Re-index a single file."""
        p = Path(filepath)
        if not p.exists():
            logger.warning("File not found: %s", filepath)
            return

        from markseek.embedder import get_model
        model = get_model(self.cfg.model_name)

        col = self.collection

        # Refresh IDs once if not already done
        self._refresh_ids()

        try:
            text = p.read_text()
        except Exception as e:
            logger.warning("Cannot read %s: %s", p.name, e)
            return

        chunks = _chunk_text(text, str(p), self.cfg)
        if not chunks:
            return

        texts = [chk["text"] for chk in chunks]
        ids = [f"{chk['file']}::{i}" for i, chk in enumerate(chunks)]
        metadatas = [{"file": chk["file"]} for chk in chunks]

        # Remove old chunks (batch delete)
        prefix = str(p) + "::"
        old_ids = [eid for eid in self._existing_ids if eid.startswith(prefix)]
        if old_ids:
            col.delete(ids=old_ids)
            for oid in old_ids:
                self._all_ids.discard(oid)

        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        col.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        self._existing_ids.update(ids)

        meta = self._load_meta()
        meta.setdefault("file_hashes", {})[str(p)] = _file_hash(p)
        self._save_meta(meta)
        logger.info("Re-indexed %s (%d chunks)", p.name, len(chunks))

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search over the indexed vault.

        Returns list of dicts with keys:
          - text: the chunk content
          - file: relative path within vault
          - score: relevance score (0-1, higher is better)
        """
        col = self.collection
        total = col.count()
        if total == 0:
            logger.info("Index is empty. Run 'markseek index' first.")
            return []

        from markseek.embedder import get_model
        model = get_model(self.cfg.model_name)
        embedding = model.encode([query]).tolist()[0]

        n = min(top_k, total)
        results = col.query(
            query_embeddings=[embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        vault = Path(self.cfg.vault_path)
        items = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            try:
                rel = Path(meta["file"]).relative_to(vault)
            except ValueError:
                rel = Path(meta["file"])
            items.append({
                "text": doc,
                "file": str(rel),
                "score": round(max(0, 1 - dist), 2),
            })
        return items
