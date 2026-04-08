"""
markseek.watcher -- Filesystem watcher for the Obsidian vault.

Watches all markdown files in the vault and automatically
re-indexes them when they change. Can run as a foreground
process or as a background daemon.
"""

import logging
import time
from pathlib import Path

from markseek.config import Config
from markseek.core import Index

logger = logging.getLogger(__name__)


class VaultWatcher:
    """Watches a vault directory for changes and re-indexes automatically."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.index = Index(cfg)
        self._pending: dict[str, float] = {}

    def start(self):
        """Start watching for file changes (blocking)."""
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        vault = Path(self.cfg.vault_path)
        if not vault.exists():
            raise FileNotFoundError(f"Vault not found: {vault}")

        class Handler(FileSystemEventHandler):
            def __init__(watcher_self):
                watcher_self.pending = self._pending

            def _maybe_track(watcher_self, event):
                if event.is_directory:
                    return
                if not any(event.src_path.endswith(ext) for ext in self.cfg.extensions):
                    return
                watcher_self.pending[event.src_path] = time.time()

            on_modified = _maybe_track
            on_created = _maybe_track

        handler = Handler()
        observer = Observer()
        observer.schedule(handler, str(vault), recursive=True)
        observer.start()

        logger.info("Watching vault: %s", vault)
        logger.info("Press Ctrl-C to stop")

        try:
            while True:
                time.sleep(1)
                now = time.time()
                ready = {
                    fp: t for fp, t in self._pending.items()
                    if now - t >= self.cfg.debounce_seconds
                }

                for fp in ready:
                    del self._pending[fp]
                    filepath = Path(fp)
                    if filepath.exists():
                        try:
                            self.index.index_file(str(filepath))
                            logger.info("✓ %s", filepath.name)
                        except Exception as e:
                            logger.error("✗ %s: %s", filepath.name, e)
        except KeyboardInterrupt:
            logger.info("Stopping watcher...")
            observer.stop()
        observer.join()
