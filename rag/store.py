from __future__ import annotations

from typing import Any

import numpy as np

from rag.models import Chunk
from rag.settings import S

COLLECTION = "wikirag"


def _client():
    import chromadb

    S.index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(S.index_dir / "chroma"))


def _meta(c: Chunk) -> dict[str, str]:
    return {
        "doc_id": c.doc_id,
        "heading": (c.heading or "")[:200],
        "classification": c.classification,
        "expires": c.expires or "",
        "acl": ",".join(c.acl),
        "dept": c.dept,
    }


def replace_collection(chunks: list[Chunk], embeddings: np.ndarray) -> Any | None:
    try:
        client = _client()
    except ImportError:
        return None
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    if len(chunks) == 0:
        return col
    col.add(
        ids=[c.id for c in chunks],
        embeddings=[[float(x) for x in row] for row in embeddings],
        documents=[c.text for c in chunks],
        metadatas=[_meta(c) for c in chunks],
    )
    return col


def open_collection() -> Any | None:
    try:
        return _client().get_collection(COLLECTION)
    except Exception:
        return None


def query_cosine(collection: Any, q_vec: np.ndarray, n: int) -> dict[str, float]:
    """Return chunk_id -> cosine similarity. Chroma cosine space stores 1 - sim as distance."""
    n = max(int(n), 1)
    res = collection.query(
        query_embeddings=[q_vec.astype(float).tolist()],
        n_results=n,
        include=["distances"],
    )
    out: dict[str, float] = {}
    for cid, dist in zip(res["ids"][0], res["distances"][0]):
        out[cid] = 1.0 - float(dist)
    return out
