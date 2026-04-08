"""
markseek.config -- Configuration management.

Reads config from:
  - ~/.config/markseek/config.yaml
  - MARKSEEK_VAULT_PATH environment variable (overrides files)

Default model: all-MiniLM-L6-v2 (80MB, CPU, fast)
Default index: ~/.cache/markseek/index/
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    vault_path: str = ""
    index_path: str = ""
    model_name: str = "all-MiniLM-L6-v2"
    max_chunk_size: int = 500
    min_chunk_size: int = 50
    top_k: int = 5
    debounce_seconds: float = 2.0
    log_level: str = "INFO"
    extensions: list = field(default_factory=lambda: [".md"])

    @classmethod
    def load(cls, config_file: str = None) -> "Config":
        """Load config with cascading priority:
        1. Environment variables (highest)
        2. Config file
        3. Defaults (lowest)
        """
        cfg = cls()

        # Config file
        if config_file is None:
            config_file = os.path.join(
                os.path.expanduser("~/.config/markseek"), "config.yaml"
            )
        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            if "vault_path" in data:
                cfg.vault_path = os.path.expanduser(data["vault_path"])
            if "index_path" in data:
                cfg.index_path = os.path.expanduser(data["index_path"])
            if "model_name" in data:
                cfg.model_name = data["model_name"]
            if "max_chunk_size" in data:
                cfg.max_chunk_size = data["max_chunk_size"]
            if "debounce_seconds" in data:
                cfg.debounce_seconds = data["debounce_seconds"]
            if "log_level" in data:
                cfg.log_level = data["log_level"]
            if "extensions" in data:
                cfg.extensions = data["extensions"]

        # Environment overrides
        vault_env = os.environ.get("MARKSEEK_VAULT_PATH")
        if vault_env:
            cfg.vault_path = os.path.expanduser(vault_env)
        elif not cfg.vault_path:
            # Fallback to Obsidian default
            cfg.vault_path = os.path.expanduser("~/Documents/Obsidian Vault")

        index_env = os.environ.get("MARKSEEK_INDEX_PATH")
        if index_env:
            cfg.index_path = os.path.expanduser(index_env)
        elif not cfg.index_path:
            cfg.index_path = os.path.expanduser("~/.cache/markseek/index")

        return cfg

    def save(self, config_file: str = None):
        """Save current config to file."""
        if config_file is None:
            config_file = os.path.join(
                os.path.expanduser("~/.config/markseek"), "config.yaml"
            )
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "vault_path": self.vault_path,
            "index_path": self.index_path,
            "model_name": self.model_name,
            "max_chunk_size": self.max_chunk_size,
            "debounce_seconds": self.debounce_seconds,
            "log_level": self.log_level,
            "extensions": self.extensions,
        }
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def vault_exists(self) -> bool:
        return bool(self.vault_path) and Path(self.vault_path).exists()
