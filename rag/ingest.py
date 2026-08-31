from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from rag.index import Index, load_index, save_index
from rag.llm import LLM
from rag.models import Chunk
from rag.settings import S
from rag.text import child_parts, parse_front_matter, split_sections

STRATEGIES = ("section", "sent_pack", "sent_only")


def load_documents(corpus_dir: Path | None = None) -> list[tuple[dict, str, Path]]:
    root = corpus_dir or S.corpus_dir
    docs = []
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() in {"readme.md", "notice.md"}:
            continue
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        docs.append((meta, body, path))
    if not docs:
        raise FileNotFoundError(f"语料为空: {root}")
    return docs


def chunk_fp(c: Chunk) -> str:
    raw = "\0".join([c.title, c.heading, c.text, c.parent_text, ",".join(c.acl), c.expires or "", c.classification])
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_chunks(docs: list[tuple[dict, str, Path]], strategy: str | None = None, corpus_root: Path | None = None) -> list[Chunk]:
    strategy = strategy or S.chunk_strategy
    root = corpus_root or S.corpus_dir
    chunks: list[Chunk] = []
    for meta, body, path in docs:
        doc_id = str(meta.get("doc_id") or path.stem)
        title = str(meta.get("title") or doc_id)
        acl = meta.get("acl") or ["engineer"]
        if isinstance(acl, str):
            acl = [acl]
        try:
            source = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            source = path.name
        for si, (heading, section) in enumerate(split_sections(body)):
            parts = child_parts(section, strategy, S.child_chars, S.child_overlap, S.pack_chars)
            for pi, (text, parent) in enumerate(parts):
                chunks.append(
                    Chunk(
                        id=f"{doc_id}#s{si}-p{pi}",
                        doc_id=doc_id,
                        title=title,
                        heading=heading,
                        text=text,
                        parent_text=parent,
                        dept=str(meta.get("dept") or "engineering"),
                        acl=list(acl),
                        classification=str(meta.get("classification") or "internal"),
                        version=str(meta.get("version") or ""),
                        expires=meta.get("expires"),
                        source=source,
                    )
                )
    return chunks


def _reuse_map(backend: str, strategy: str) -> dict[str, np.ndarray]:
    try:
        old = load_index()
    except FileNotFoundError:
        return {}
    meta: dict = {}
    p = S.index_dir / "meta.json"
    if p.exists():
        meta = json.loads(p.read_text(encoding="utf-8"))
    if meta.get("backend") != backend or meta.get("strategy") != strategy:
        return {}
    return {chunk_fp(c): old.embeddings[i] for i, c in enumerate(old.chunks) if i < len(old.embeddings)}


def ingest(strategy: str | None = None) -> None:
    strategy = strategy or S.chunk_strategy
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy}, expected {STRATEGIES}")
    llm = LLM()
    docs = load_documents()
    chunks = build_chunks(docs, strategy, corpus_root=S.corpus_dir)
    backend = llm.embed_kind
    reused = _reuse_map(backend, strategy)
    texts, fresh_idx = [], []
    vecs: list[np.ndarray | None] = [None] * len(chunks)
    for i, c in enumerate(chunks):
        prev = reused.get(chunk_fp(c))
        if prev is not None:
            vecs[i] = prev
        else:
            texts.append(f"{c.title}\n{c.heading}\n{c.text}")
            fresh_idx.append(i)
    if texts:
        new = llm.embed(texts)
        for row, i in enumerate(fresh_idx):
            vecs[i] = new[row]
    embeddings = np.stack(vecs) if vecs else llm.embed([])
    vs = save_index(chunks, embeddings, backend, extra={"strategy": strategy, "reused": len(chunks) - len(fresh_idx)})
    print(
        f"ingested {len(docs)} docs / {len(chunks)} chunks  strategy={strategy}  "
        f"backend={backend}  vector_store={vs}  reused={len(chunks) - len(fresh_idx)}  dim={embeddings.shape[1]}"
    )


def build_index_memory(strategy: str, llm: LLM) -> Index:
    chunks = build_chunks(load_documents(), strategy, corpus_root=S.corpus_dir)
    emb = llm.embed([f"{c.title}\n{c.heading}\n{c.text}" for c in chunks])
    backend = llm.embed_kind
    return Index(chunks, emb, backend=backend)


if __name__ == "__main__":
    ingest()
