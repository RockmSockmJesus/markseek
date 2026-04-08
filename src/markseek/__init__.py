"""
markseek -- Semantic search over your markdown vault.
"""

__version__ = "0.1.1"
__all__ = ["Index", "Config", "VaultWatcher"]

from markseek.core import Index
from markseek.config import Config
from markseek.watcher import VaultWatcher
