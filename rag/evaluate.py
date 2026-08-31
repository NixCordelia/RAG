from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from rag.agent import run_agent
from rag.index import Index, load_index
from rag.ingest import STRATEGIES, build_index_memory
from rag.llm import LLM
from rag.models import Answer
from rag.retrieve import retrieve
from rag.settings import S
from rag.text import overlap_count, tokenize
from rag.users import parse_user


def load_gold(path: Path | None = None) -> list[dict]:
    p = path or S.gold_path
    items = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _hit_at_k(expected: list[str], got_docs: list[str], k: int) -> float:
    if not expected:
        return 1.0
    return 1.0 if any(d in got_docs[:k] for d in expected) else 0.0


def _mrr(expected: list[str], got_docs: list[str]) -> float:
    if not expected:
        return 0.0
    for i, d in enumerate(got_docs, 1):
        if d in expected:
            return 1.0 / i
    return 0.0


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    k = (len(ys) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(ys) - 1)
    w = k - lo
    return round(ys[lo] * (1 - w) + ys[hi] * w, 2)


def groundedness(ans: Answer, index: Index) -> float:
    """Lexical overlap of the answer with cited child+parent text. Refusals count as 1."""
    if ans.refused:
        return 1.0
    if not ans.citations:
        return 0.0
    pieces = []
    for cid in ans.citations:
        ch = index.by_id.get(cid)
        if not ch:
            return 0.0
        pieces.append(f"{ch.title} {ch.heading} {ch.text} {ch.parent_text}")
    src, at = set(tokenize(" ".join(pieces))), set(tokenize(ans.text))
    if not at:
        return 0.0
    return round(len(at & src) / len(at), 4)


def keypoint_coverage(text: str, keys: list[str]) -> float | None:
    """答案是否覆盖金标要点。用 | 表示中英同义，命中任一即可。"""
    if not keys:
        return None
    blob = (text or "").lower()
    hit = 0
    for k in keys:
        alts = [a.strip() for a in str(k).split("|") if a.strip()]
        if not alts:
            continue
        if any(a.lower() in blob or overlap_count(a, text or "") >= 1 for a in alts):
            hit += 1
    return round(hit / len(keys), 4)


def _answerable(gold: list[dict]) -> list[dict]:
    return [g for g in gold if g.get("expected_behavior") == "answer"]


def _retrieval_run(index: Index, gold: list[dict], llm: LLM, mode: str) -> dict:
    hits, mrrs, times = [], [], []
    for item in gold:
        user = parse_user(item.get("user", "engineer"))
        t0 = time.perf_counter()
        got = [h.chunk.doc_id for h in retrieve(item["question"], user, index, mode=mode, llm=llm)]  # type: ignore[arg-type]
        times.append((time.perf_counter() - t0) * 1000)
        expected = list(item.get("expected_doc_ids") or [])
        hits.append(_hit_at_k(expected, got, 5))
        mrrs.append(_mrr(expected, got))
    n = len(hits) or 1
    return {
        "hit@5": round(sum(hits) / n, 4),
        "mrr": round(sum(mrrs) / n, 4),
        "retrieve_p50_ms": _pct(times, 50),
        "retrieve_p95_ms": _pct(times, 95),
        "n_chunks": len(index.chunks),
    }


def evaluate(mode: str = "hybrid_rerank") -> dict:
    llm = LLM()
    index = load_index()
    gold = load_gold()
    retrieval_rows = []
    e2e_rows = []
    leak = 0
    faiths: list[float] = []
    keypoints: list[float] = []
    e2e_ms: list[float] = []
    retrieve_ms: list[float] = []
    by_type: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for item in gold:
        user = parse_user(item.get("user", "engineer"))
        q = item["question"]
        expected = list(item.get("expected_doc_ids") or [])
        qtype = item.get("type", "single")
        behavior = item.get("expected_behavior", "answer")

        t0 = time.perf_counter()
        hits = retrieve(q, user, index, mode=mode, llm=llm)  # type: ignore[arg-type]
        retrieve_ms.append((time.perf_counter() - t0) * 1000)
        got_docs = [h.chunk.doc_id for h in hits]
        leak_now = any(not user.can_read(h.chunk) for h in hits)

        hit = _hit_at_k(expected, got_docs, 5) if behavior == "answer" else None
        mrr = _mrr(expected, got_docs) if behavior == "answer" else None
        retrieval_rows.append({"id": item["id"], "type": qtype, "hit@5": hit, "mrr": mrr, "docs": got_docs[:5]})
        if hit is not None:
            by_type[qtype]["hit@5"].append(hit)
            by_type[qtype]["mrr"].append(mrr or 0.0)

        ans = run_agent(q, user, index, llm=llm)
        e2e_ms.append(ans.latency_ms)
        g = groundedness(ans, index)
        faiths.append(g)
        cite_docs = []
        for cid in ans.citations:
            ch = index.by_id.get(cid)
            if ch:
                cite_docs.append(ch.doc_id)
                if not user.can_read(ch):
                    leak_now = True
        if leak_now:
            leak += 1

        refuse_ok = True
        if behavior == "refuse_no_evidence":
            refuse_ok = ans.refused and ans.refuse_reason == "no_evidence"
        elif behavior == "refuse_expired":
            refuse_ok = ans.refused and ans.refuse_reason == "expired"
        elif behavior == "refuse_acl":
            refuse_ok = ans.refused and not leak_now
        elif behavior == "answer":
            refuse_ok = (not ans.refused) and (not expected or any(d in cite_docs or d in got_docs for d in expected))

        e2e_rows.append(
            {
                "id": item["id"],
                "type": qtype,
                "behavior": behavior,
                "ok": refuse_ok,
                "refused": ans.refused,
                "reason": ans.refuse_reason,
                "mode": ans.mode,
                "groundedness": g,
                "latency_ms": ans.latency_ms,
            }
        )
        by_type[qtype]["e2e"].append(1.0 if refuse_ok else 0.0)
        by_type[qtype]["groundedness"].append(g)
        kp = list(item.get("expected_keypoints") or [])
        if behavior == "answer" and kp:
            cov = 0.0 if ans.refused else (keypoint_coverage(ans.text, kp) or 0.0)
            keypoints.append(cov)
            by_type[qtype]["keypoint"].append(cov)

    n_ans = sum(1 for r in retrieval_rows if r["hit@5"] is not None) or 1
    report = {
        "mode": mode,
        "n": len(gold),
        "embed": llm.embed_kind,
        "chat": "chat" if llm.can_chat else "extractive",
        "hit@5": round(sum(r["hit@5"] or 0 for r in retrieval_rows) / n_ans, 4),
        "mrr": round(sum(r["mrr"] or 0 for r in retrieval_rows) / n_ans, 4),
        "acl_leak_rate": round(leak / max(len(gold), 1), 4),
        "e2e_ok": round(sum(1 for r in e2e_rows if r["ok"]) / len(e2e_rows), 4),
        "groundedness": round(sum(faiths) / len(faiths), 4) if faiths else 0.0,
        "keypoint_coverage": round(sum(keypoints) / len(keypoints), 4) if keypoints else None,
        "retrieve_p50_ms": _pct(retrieve_ms, 50),
        "retrieve_p95_ms": _pct(retrieve_ms, 95),
        "e2e_p50_ms": _pct(e2e_ms, 50),
        "e2e_p95_ms": _pct(e2e_ms, 95),
        "tokens": llm.tokens,
        "by_type": {
            t: {k: round(sum(v) / len(v), 4) for k, v in metrics.items() if v}
            for t, metrics in by_type.items()
        },
        "retrieval": retrieval_rows,
        "e2e": e2e_rows,
    }
    S.eval_dir.mkdir(parents=True, exist_ok=True)
    out = S.eval_dir / "last_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(report)
    keys = (
        "mode",
        "n",
        "embed",
        "chat",
        "hit@5",
        "mrr",
        "acl_leak_rate",
        "e2e_ok",
        "groundedness",
        "keypoint_coverage",
        "retrieve_p50_ms",
        "retrieve_p95_ms",
        "e2e_p50_ms",
        "e2e_p95_ms",
        "tokens",
        "by_type",
    )
    print(json.dumps({k: report[k] for k in keys}, ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return report


def _write_md(report: dict) -> None:
    lines = [
        f"# Eval report (`{report['mode']}`)",
        "",
        f"- embed: `{report['embed']}`  chat: `{report['chat']}`  n={report['n']}  tokens={report.get('tokens', 0)}",
        f"- Hit@5 (answerable): **{report['hit@5']}**  MRR: **{report['mrr']}**",
        f"- ACL leak rate: **{report['acl_leak_rate']}** (target 0)",
        f"- E2E behavior: **{report['e2e_ok']}**  groundedness: **{report['groundedness']}**  keypoints: **{report.get('keypoint_coverage')}**",
        f"- retrieve p50/p95: **{report['retrieve_p50_ms']} / {report['retrieve_p95_ms']} ms**",
        f"- e2e p50/p95: **{report['e2e_p50_ms']} / {report['e2e_p95_ms']} ms**",
        "",
        "| type | hit@5 | mrr | e2e | groundedness | keypoint |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for t, m in sorted(report["by_type"].items()):
        lines.append(
            f"| {t} | {m.get('hit@5', '-')} | {m.get('mrr', '-')} | {m.get('e2e', '-')} | {m.get('groundedness', '-')} | {m.get('keypoint', '-')} |"
        )
    (S.eval_dir / "last_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ablation() -> None:
    llm = LLM()
    index = load_index()
    gold = _answerable(load_gold())
    print(f"{'mode':<16} {'hit@5':>8} {'mrr':>8} {'p50ms':>8} {'p95ms':>8}")
    rows = []
    for mode in ("dense", "bm25", "hybrid", "hybrid_rerank"):
        rec = {"mode": mode, **_retrieval_run(index, gold, llm, mode)}
        rows.append(rec)
        print(f"{mode:<16} {rec['hit@5']:8.4f} {rec['mrr']:8.4f} {rec['retrieve_p50_ms']:8.2f} {rec['retrieve_p95_ms']:8.2f}")
    S.eval_dir.mkdir(parents=True, exist_ok=True)
    (S.eval_dir / "ablation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def chunk_ablation() -> None:
    """同一评测集、三种切分。只测检索，不覆盖磁盘索引。"""
    llm = LLM()
    gold = _answerable(load_gold())
    print(f"{'strategy':<12} {'chunks':>7} {'hit@5':>8} {'mrr':>8} {'p50ms':>8}")
    rows = []
    for strat in STRATEGIES:
        index = build_index_memory(strat, llm)
        rec = {"strategy": strat, **_retrieval_run(index, gold, llm, "hybrid_rerank")}
        rows.append(rec)
        print(f"{strat:<12} {rec['n_chunks']:7d} {rec['hit@5']:8.4f} {rec['mrr']:8.4f} {rec['retrieve_p50_ms']:8.2f}")
    S.eval_dir.mkdir(parents=True, exist_ok=True)
    (S.eval_dir / "chunk_ablation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def paraphrase_eval(mode: str = "hybrid_rerank") -> dict:
    """原题 vs 改写题的检索对照，用来检查 Hit@5 是不是背题。"""
    if not S.gold_paraphrase_path.exists():
        raise RuntimeError(f"缺少改写集 {S.gold_paraphrase_path}")
    llm = LLM()
    index = load_index()
    orig = _retrieval_run(index, _answerable(load_gold()), llm, mode)
    para = _retrieval_run(index, _answerable(load_gold(S.gold_paraphrase_path)), llm, mode)
    report = {
        "mode": mode,
        "embed": llm.embed_kind,
        "original": orig,
        "paraphrase": para,
        "n_original": orig.get("n_chunks"),
        "note": "只测检索。改写题与金标同一 expected_doc_ids，问法不同。",
    }
    S.eval_dir.mkdir(parents=True, exist_ok=True)
    out = S.eval_dir / "paraphrase_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# 改写题检索对照",
        "",
        f"mode `{mode}` embed `{llm.embed_kind}`",
        "",
        "| 集合 | Hit@5 | MRR | p50 ms |",
        "|---|---:|---:|---:|",
        f"| 原金标可答题 | {orig['hit@5']} | {orig['mrr']} | {orig['retrieve_p50_ms']} |",
        f"| 改写题 | {para['hit@5']} | {para['mrr']} | {para['retrieve_p50_ms']} |",
        "",
        "改写集：`data/goldenset_paraphrase.jsonl`。明显掉点说明原 Hit@5 对问法过拟合。",
        "",
    ]
    (S.eval_dir / "paraphrase_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"original": orig, "paraphrase": para}, ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ablation", action="store_true")
    p.add_argument("--chunks", action="store_true", help="切分策略消融（内存索引，不改磁盘）")
    p.add_argument("--paraphrase", action="store_true", help="改写题 vs 原题检索对照")
    p.add_argument("--ragas", action="store_true", help="Ragas 检索与可信度")
    p.add_argument("--mode", default="hybrid_rerank")
    args = p.parse_args()
    if args.chunks:
        chunk_ablation()
    elif args.ablation:
        ablation()
    elif args.paraphrase:
        paraphrase_eval(args.mode)
    elif args.ragas:
        from rag.ragas_eval import run_ragas

        run_ragas(args.mode)
    else:
        evaluate(args.mode)


if __name__ == "__main__":
    main()
