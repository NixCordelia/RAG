from __future__ import annotations

import re

import numpy as np

from rag.index import Index
from rag.llm import LLM
from rag.models import Hit, RetrieveMode, User
from rag.settings import S
from rag.store import query_cosine
from rag.synonyms import extra_queries
from rag.text import overlap_count, tokenize

_SPLIT = re.compile(r"同时|而要用|而要|还要检查|还要|除了")


def expand_queries(query: str) -> list[str]:
    """原句 + 并列拆分 + 领域同义词，供多路 RRF。"""
    q = (query or "").strip()
    if not q:
        return []
    out: list[str] = [q]
    for part in _SPLIT.split(q):
        part = part.strip(" ，,、的是？?。")
        if len(part) >= 6 and part not in out:
            out.append(part)
    for extra in extra_queries(q):
        if extra not in out:
            out.append(extra)
    return out[:4]


def unique_by_doc(hits: list[Hit]) -> list[Hit]:
    seen: set[str] = set()
    out: list[Hit] = []
    for h in hits:
        did = h.chunk.doc_id
        if did in seen:
            continue
        seen.add(did)
        out.append(h)
    return out


def cutoff_docs(docs: list[Hit], k: int, rel: float) -> list[Hit]:
    """丢掉相对头名明显更弱的文档，少往 Top-K 里塞近邻杂质。"""
    if not docs:
        return []
    k = max(1, k)
    top = float(docs[0].score)
    kept: list[Hit] = []
    for h in docs:
        if len(kept) >= k:
            break
        if not kept:
            kept.append(h)
            continue
        if top <= 0:
            if len(kept) < min(2, k):
                kept.append(h)
            else:
                break
            continue
        ratio = float(h.score) / top
        if ratio >= rel or (len(kept) < 2 and ratio >= rel * 0.7):
            kept.append(h)
        else:
            break
    return kept


def _minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-8:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def _rrf(rank_lists: list[list[int]], k: int) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for r, idx in enumerate(ranks):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + r + 1)
    return scores


def _dense_scores(index: Index, q_vec: np.ndarray, allowed: list[int]) -> np.ndarray:
    if not allowed:
        return np.zeros(0, dtype=np.float32)
    if index.chroma is None:
        return index.embeddings[allowed] @ q_vec
    try:
        sim = query_cosine(index.chroma, q_vec, n=len(index.chunks))
    except Exception:
        return index.embeddings[allowed] @ q_vec
    out = np.array([sim.get(index.chunks[i].id, -1.0) for i in allowed], dtype=np.float32)
    if np.all(out < 0):
        return index.embeddings[allowed] @ q_vec
    return out


def _blob(h: Hit) -> str:
    c = h.chunk
    return f"{c.title} {c.heading} {c.text}"


def _select_hits(raw: list[Hit], chunk_k: int, doc_k: int, queries: list[str]) -> list[Hit]:
    uniq = unique_by_doc(raw)
    if queries:
        lexical = [h for h in uniq if any(overlap_count(q, _blob(h)) >= 1 for q in queries)]
        if lexical:
            uniq = lexical
    kept_docs = {h.chunk.doc_id for h in cutoff_docs(uniq, doc_k, S.score_rel)}
    return [h for h in raw if h.chunk.doc_id in kept_docs][:chunk_k]


def retrieve(
    query: str,
    user: User,
    index: Index,
    k: int | None = None,
    mode: RetrieveMode = "hybrid_rerank",
    llm: LLM | None = None,
) -> list[Hit]:
    """ACL is applied before scoring. Unauthorized chunks never leave the store."""
    k = k or S.retrieve_k
    allowed = index.allowed_indices(user)
    queries = expand_queries(query)
    if not allowed or not queries:
        return []

    llm = llm or LLM()
    vecs = llm.embed(queries)
    n = len(allowed)
    pool = max(k * 3, 12)
    dense_sum = np.zeros(n, dtype=np.float32)
    bm25_sum = np.zeros(n, dtype=np.float32)
    rank_lists: list[list[int]] = []

    for i, q in enumerate(queries):
        dense = _dense_scores(index, vecs[i], allowed)
        bm25 = index.bm25.scores(tokenize(q))[allowed]
        dense_sum += dense
        bm25_sum += bm25
        rank_lists.append(np.argsort(-dense)[:pool].tolist())
        rank_lists.append(np.argsort(-bm25)[:pool].tolist())

    dense = dense_sum / max(len(queries), 1)
    bm25 = bm25_sum / max(len(queries), 1)

    if mode == "dense":
        order = np.argsort(-dense).tolist()
        raw = dense
    elif mode == "bm25":
        order = np.argsort(-bm25).tolist()
        raw = bm25
    elif mode == "hybrid":
        rrf = _rrf(rank_lists, S.rrf_k)
        order = sorted(rrf, key=lambda i: rrf[i], reverse=True)
        raw = np.array([rrf.get(i, 0.0) for i in range(n)], dtype=np.float32)
    else:
        rrf = _rrf(rank_lists, S.rrf_k)
        cand = sorted(rrf, key=lambda i: rrf[i], reverse=True)[: max(pool, 20)]
        fused = S.dense_weight * _minmax(dense) + (1 - S.dense_weight) * _minmax(bm25)
        cand.sort(key=lambda i: float(fused[i]), reverse=True)
        order = cand
        raw = fused

    hits: list[Hit] = []
    for local in order[: max(k * 4, 24)]:
        d_sc = float(dense[local])
        b_sc = float(bm25[local])
        if b_sc <= 0 and (index.backend == "hash" or d_sc < 0.15):
            continue
        chunk = index.chunks[allowed[local]]
        hits.append(Hit(chunk=chunk, score=float(raw[local]), expired=chunk.expired))
    return _select_hits(hits, k, S.retrieve_doc_k, queries)
