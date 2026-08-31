"""Ragas 评测：检索准确（context precision/recall）与回答可信（faithfulness）。

无 EVAL_API_KEY / OPENAI_API_KEY 时只跑 ID / Non-LLM 指标（不调评测模型）。
评测裁判走 EVAL_*（未配则回退 OPENAI_*），与 Agent 生成网关可以不是同一家。
"""

from __future__ import annotations

import asyncio
import json
import math
from statistics import mean
from typing import Any

from rag.agent import run_agent
from rag.evaluate import groundedness, load_gold
from rag.index import Index, load_index
from rag.llm import LLM
from rag.models import Hit, User
from rag.retrieve import retrieve
from rag.settings import S
from rag.users import parse_user


def _uniq(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _finite(xs: list[float]) -> list[float]:
    return [x for x in xs if isinstance(x, (int, float)) and math.isfinite(float(x))]


def _avg(xs: list[float]) -> float | None:
    ys = _finite(xs)
    return round(mean(ys), 4) if ys else None


ID_AT = 5
NONLLM_THRESHOLD = 0.4


def _chunk_text(c) -> str:
    return f"{c.title}\n{c.heading}\n{c.text}"


def reference_contexts(index: Index, user: User, doc_ids: list[str], question: str = "") -> list[str]:
    """与命中块同粒度；有问题时只保留和问句有重叠的参考块。"""
    wanted = set(doc_ids)
    cands = [c for c in index.chunks if c.doc_id in wanted and user.can_read(c)]
    if question:
        from rag.text import overlap_count

        ranked = sorted(cands, key=lambda c: overlap_count(question, _chunk_text(c)), reverse=True)
        picked = [c for c in ranked if overlap_count(question, _chunk_text(c)) >= 1][:6]
        if picked:
            cands = picked
    return [_chunk_text(c) for c in cands]


def retrieved_texts(hits: list[Hit]) -> list[str]:
    return [_chunk_text(h.chunk) for h in hits]


def pack_sample(
    item: dict,
    user: User,
    hits: list[Hit],
    answer_text: str,
    index: Index,
) -> dict[str, Any]:
    expected = list(item.get("expected_doc_ids") or [])
    refs = reference_contexts(index, user, expected, item.get("question") or "")
    ranked_docs = _uniq([h.chunk.doc_id for h in hits])
    return {
        "id": item["id"],
        "type": item.get("type", "single"),
        "behavior": item.get("expected_behavior", "answer"),
        "user_input": item["question"],
        "response": answer_text,
        "retrieved_context_ids": ranked_docs[:ID_AT],
        "reference_context_ids": list(expected),
        "retrieved_contexts": retrieved_texts(hits[:ID_AT]),
        "reference_contexts": refs,
        "reference": "\n\n".join(refs)[:8000],
    }


def _need_ragas() -> None:
    try:
        import ragas  # noqa: F401
    except ImportError as e:
        raise RuntimeError("Ragas 未安装：pip install -r requirements-eval.txt") from e


async def _score_retrieval(samples: list[dict]) -> list[dict]:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import (
        IDBasedContextPrecision,
        IDBasedContextRecall,
        NonLLMContextPrecisionWithReference,
        NonLLMContextRecall,
    )

    id_p, id_r = IDBasedContextPrecision(), IDBasedContextRecall()
    nl_p = NonLLMContextPrecisionWithReference(threshold=NONLLM_THRESHOLD)
    nl_r = NonLLMContextRecall(threshold=NONLLM_THRESHOLD)
    rows = []
    for raw in samples:
        if raw["behavior"] != "answer":
            continue
        if not raw["reference_context_ids"]:
            continue
        row = {"id": raw["id"], "type": raw["type"]}
        if raw["retrieved_context_ids"]:
            sid = SingleTurnSample(
                retrieved_context_ids=raw["retrieved_context_ids"],
                reference_context_ids=raw["reference_context_ids"],
            )
            row["id_context_precision"] = float(await id_p.single_turn_ascore(sid))
            row["id_context_recall"] = float(await id_r.single_turn_ascore(sid))
        else:
            row["id_context_precision"] = 0.0
            row["id_context_recall"] = 0.0
        if raw["retrieved_contexts"] and raw["reference_contexts"]:
            nls = SingleTurnSample(
                retrieved_contexts=raw["retrieved_contexts"],
                reference_contexts=raw["reference_contexts"],
            )
            row["nonllm_context_precision"] = float(await nl_p.single_turn_ascore(nls))
            row["nonllm_context_recall"] = float(await nl_r.single_turn_ascore(nls))
        rows.append(row)
    return rows


async def _score_llm(samples: list[dict]) -> list[dict]:
    from langchain_openai import ChatOpenAI
    from ragas.dataset_schema import SingleTurnSample
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, LLMContextRecall

    chat = ChatOpenAI(
        model=S.eval_chat_model,
        api_key=S.eval_api_key,
        base_url=S.eval_base_url,
        temperature=0,
    )
    judge = LangchainLLMWrapper(chat)
    faith = Faithfulness(llm=judge)
    recall = LLMContextRecall(llm=judge)
    rows = []
    for raw in samples:
        if raw["behavior"] != "answer" or not raw["retrieved_contexts"] or not raw["reference"]:
            continue
        sample = SingleTurnSample(
            user_input=raw["user_input"],
            response=raw["response"],
            retrieved_contexts=raw["retrieved_contexts"],
            reference=raw["reference"],
        )
        row = {"id": raw["id"]}
        try:
            row["faithfulness"] = float(await faith.single_turn_ascore(sample))
        except Exception as e:
            row["faithfulness_error"] = str(e)
        try:
            row["llm_context_recall"] = float(await recall.single_turn_ascore(sample))
        except Exception as e:
            row["llm_context_recall_error"] = str(e)
        rows.append(row)
    return rows


def run_ragas(mode: str = "hybrid_rerank") -> dict:
    _need_ragas()
    llm = LLM()
    index = load_index()
    gold = load_gold()
    packed: list[dict] = []
    faith_lex: list[float] = []

    for item in gold:
        user = parse_user(item.get("user", "engineer"))
        hits = retrieve(item["question"], user, index, mode=mode, llm=llm)  # type: ignore[arg-type]
        ans = run_agent(item["question"], user, index, llm=llm)
        packed.append(pack_sample(item, user, hits, ans.text, index))
        faith_lex.append(groundedness(ans, index))

    retrieval_rows = asyncio.run(_score_retrieval(packed))
    llm_rows: list[dict] = []
    if S.can_judge():
        llm_rows = asyncio.run(_score_llm(packed))
    else:
        print("未配置 EVAL_API_KEY / OPENAI_API_KEY：跳过 Faithfulness / LLMContextRecall（裁判与生成网关可分开配）")

    report = {
        "framework": "ragas",
        "ragas_note": f"id_* 为文档 id 的 Precision/Recall@{ID_AT}；nonllm_* 为块对块 RapidFuzz（阈值 {NONLLM_THRESHOLD}）；faithfulness 用 EVAL_* 或 OPENAI_* 裁判",
        "id_at": ID_AT,
        "mode": mode,
        "n": len(gold),
        "n_answerable": sum(1 for p in packed if p["behavior"] == "answer"),
        "embed": llm.embed_kind,
        "chat": "chat" if llm.can_chat else "extractive",
        "judge": S.eval_chat_model if S.can_judge() else None,
        "id_context_precision": _avg([r["id_context_precision"] for r in retrieval_rows if "id_context_precision" in r]),
        "id_context_recall": _avg([r["id_context_recall"] for r in retrieval_rows if "id_context_recall" in r]),
        "nonllm_context_precision": _avg(
            [r["nonllm_context_precision"] for r in retrieval_rows if "nonllm_context_precision" in r]
        ),
        "nonllm_context_recall": _avg(
            [r["nonllm_context_recall"] for r in retrieval_rows if "nonllm_context_recall" in r]
        ),
        "faithfulness": _avg([r["faithfulness"] for r in llm_rows if "faithfulness" in r]),
        "llm_context_recall": _avg([r["llm_context_recall"] for r in llm_rows if "llm_context_recall" in r]),
        "lexical_groundedness": _avg(faith_lex),
        "retrieval": retrieval_rows,
        "llm_metrics": llm_rows,
    }
    S.eval_dir.mkdir(parents=True, exist_ok=True)
    out = S.eval_dir / "ragas_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(report)
    summary = {k: report[k] for k in report if k not in ("retrieval", "llm_metrics")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return report


def _write_md(report: dict) -> None:
    lines = [
        "# Ragas 评测",
        "",
        f"- mode `{report['mode']}`  embed `{report['embed']}`  chat `{report['chat']}`  n={report['n']}",
        f"- ID Context Precision@{report.get('id_at', 5)}: **{report['id_context_precision']}**  Recall: **{report['id_context_recall']}**",
        f"- Non-LLM Context Precision: **{report['nonllm_context_precision']}**  Recall: **{report['nonllm_context_recall']}**",
        f"- Faithfulness (judge): **{report['faithfulness']}**  LLM Context Recall: **{report['llm_context_recall']}**",
        f"- 词面 groundedness（对照）: **{report['lexical_groundedness']}**",
        "",
        "ID 指标看 Top-5 去重后的文档 id。Non-LLM 为命中块 vs 参考文档中的块（同粒度）。Faithfulness 使用 EVAL_* 网关，未配则回退 OPENAI_*。",
        "",
    ]
    (S.eval_dir / "ragas_report.md").write_text("\n".join(lines), encoding="utf-8")
