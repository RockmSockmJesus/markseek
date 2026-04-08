"""
markseek.embedder -- Lazy-loaded embedding model.

Caches the model on first use. Uses environment-variable-aware
device selection (CPU-only for maximum compatibility).
"""

import os
from typing import Optional

_model_cache: dict = {}


def get_model(model_name: str = "all-MiniLM-L6-v2"):
    """Load and return a SentenceTransformer model (cached).

    Forces CPU device regardless of GPU availability. This is
    because:
    1. The small models are fast enough on CPU
    2. GPU dependencies (nvidia libraries) add hundreds of MBs
    3. Works everywhere -- laptops, servers, containers
    """
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        _model_cache[model_name] = SentenceTransformer(
            model_name,
            device="cpu",
        )
    return _model_cache[model_name]
