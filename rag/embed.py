from __future__ import annotations

import hashlib

import numpy as np

HASH_DIM = 384


def hashed_embed(texts: list[str], dim: int = HASH_DIM) -> np.ndarray:
    """Signed feature hashing. Offline fallback so clone-and-run needs no API key."""
    from rag.text import tokenize

    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        for tok in tokenize(text):
            digest = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            out[i, idx] += sign
        n = float(np.linalg.norm(out[i]))
        if n:
            out[i] /= n
    return out


def l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    return (mat / norms).astype(np.float32)


_m3e_cache: dict[str, object] = {}


def m3e_embed(texts: list[str], model_name: str) -> np.ndarray:
    """Local M3E via sentence-transformers. Model is loaded once per process."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError("本地 M3E 需要: pip install -r requirements-m3e.txt") from e
    model = _m3e_cache.get(model_name)
    if model is None:
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            model = SentenceTransformer(model_name)
        _m3e_cache[model_name] = model
    vec = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vec, dtype=np.float32)
