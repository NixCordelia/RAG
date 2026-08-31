from __future__ import annotations

from dataclasses import fields
import json
import numpy as np

from rag.bm25 import BM25
from rag.models import Chunk
from rag.settings import S
from rag.store import open_collection, replace_collection
from rag.text import tokenize


class Index:
    def __init__(self, chunks: list[Chunk], embeddings: np.ndarray, backend: str = "hash", chroma=None):
        self.chunks = chunks
        self.embeddings = embeddings
        self.backend = backend
        self.chroma = chroma
        self.by_id = {c.id: c for c in chunks}
        self.bm25 = BM25([tokenize(f"{c.title} {c.heading} {c.text}") for c in chunks])

    def allowed_indices(self, user) -> list[int]:
        return [i for i, c in enumerate(self.chunks) if user.can_read(c)]

    def parent_of(self, chunk_id: str) -> Chunk | None:
        """按 id 取块；完整段落在 chunk.parent_text。"""
        return self.by_id.get(chunk_id)


def save_index(chunks: list[Chunk], embeddings: np.ndarray, backend: str, extra: dict | None = None) -> str:
    S.index_dir.mkdir(parents=True, exist_ok=True)
    path = S.index_dir / "chunks.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")
    np.save(S.index_dir / "embeddings.npy", embeddings)
    col = replace_collection(chunks, embeddings)
    vs = "chroma" if col is not None else "numpy"
    meta = {
        "n": len(chunks),
        "dim": int(embeddings.shape[1]) if len(chunks) else 0,
        "backend": backend,
        "vector_store": vs,
    }
    meta.update(extra or {})
    meta["vector_store"] = vs
    (S.index_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta["vector_store"]


def load_index() -> Index:
    path = S.index_dir / "chunks.jsonl"
    npy = S.index_dir / "embeddings.npy"
    if not path.exists() or not npy.exists():
        raise FileNotFoundError("索引不存在，请先运行 python -m rag ingest")
    chunks: list[Chunk] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            allowed = {f.name for f in fields(Chunk)}
            chunks.append(Chunk(**{k: v for k, v in d.items() if k in allowed}))
    embeddings = np.load(npy)
    meta_path = S.index_dir / "meta.json"
    backend = "hash"
    if meta_path.exists():
        backend = json.loads(meta_path.read_text(encoding="utf-8")).get("backend", "hash")
    return Index(chunks, embeddings, backend=backend, chroma=open_collection())


def index_exists() -> bool:
    return (S.index_dir / "chunks.jsonl").exists() and (S.index_dir / "embeddings.npy").exists()
