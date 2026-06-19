"""Local, credit-free embeddings for the vector index.

Uses fastembed (ONNX on CPU — no torch, no API). Default model is
mixedbread-ai/mxbai-embed-large-v1 (1024-dim) — the strongest open-weight
embedder we can run CPU-only here (the 7B MTEB leaders need a GPU). Must match
PRIOR_EMBED_DIM=1024 and the Neo4j vector index. Downloads once, then cached.
"""

from __future__ import annotations

import os
from functools import lru_cache

_MODEL = os.environ.get("PRIOR_EMBED_MODEL", "mixedbread-ai/mxbai-embed-large-v1")


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts → list of vectors (plain floats for Neo4j)."""
    if not texts:
        return []
    return [v.tolist() for v in _model().embed(texts)]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
