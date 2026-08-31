from __future__ import annotations

import json
import re
import time

from rag.index import Index
from rag.llm import LLM, parse_json_object
from rag.models import Answer, Hit, TraceStep, User
from rag.retrieve import retrieve
from rag.settings import S
from rag.text import overlap_count, split_sentences, tokenize

SYSTEM = """你是内部 Wiki 知识库助手。只能依据工具返回的资料作答，禁止使用自身记忆补全事实。
检索结果里不会出现当前身份无权阅读的内容，不要猜测「是否存在机密文档」。
若资料不足、互相矛盾或全部过期，必须拒绝作答。
带 [EXPIRED] 的块不能当现行依据：若问题依赖过期页，输出 refuse / expired，不要改写成「仍可以使用」。
答案只用资料里出现的名称、端口、步骤，禁止补充未出现的操作。

每轮只输出一个 JSON 对象，不要 Markdown：
{"tool":"search","query":"改写后的检索词"}
{"tool":"read","chunk_id":"文档块id"}
{"tool":"answer","text":"答案","citations":["chunk_id"]}
{"tool":"refuse","reason":"no_evidence"|"expired","detail":"原因"}

策略：先 search；需要完整段落时 read；多跳问题拆成多次 search。
答案必须可被 citations 中的原文支持，并在句末用 [chunk_id] 标注。"""


def _hits_obs(hits: list[Hit]) -> str:
    if not hits:
        return "检索结果为空（无权限或无匹配）。"
    lines = []
    for h in hits:
        flag = " [EXPIRED]" if h.expired else ""
        lines.append(
            f"- {h.chunk.id}{flag} score={h.score:.3f} 《{h.chunk.title}》/{h.chunk.heading}\n  {h.chunk.text}"
        )
    return "\n".join(lines)


def _blob(h: Hit) -> str:
    c = h.chunk
    return f"{c.title} {c.heading} {c.text} {c.parent_text}"


def token_groundedness(text: str, hits: list[Hit]) -> float:
    if not hits or not text.strip():
        return 0.0
    src, at = set(tokenize(" ".join(_blob(h) for h in hits))), set(tokenize(text))
    if not at:
        return 0.0
    return len(at & src) / len(at)


def constrain_to_evidence(text: str, hits: list[Hit]) -> str:
    """丢掉引用块里完全对不上的句子/清单项，避免排障题补训练记忆。"""
    if not text.strip() or not hits:
        return text
    blob = " ".join(_blob(h) for h in hits)
    kept: list[str] = []
    for sent in split_sentences(text):
        bits = [b.strip() for b in re.split(r"[、；;]|以及", sent) if b.strip()]
        if len(bits) >= 3:
            ok = [b for b in bits if overlap_count(b, blob) >= 1]
            if ok:
                kept.append("、".join(ok))
            continue
        if overlap_count(sent, blob) >= 1 or token_groundedness(sent, hits) >= 0.3:
            kept.append(sent)
    return "\n".join(kept).strip()


def useful_hits(question: str, hits: list[Hit]) -> list[Hit]:
    return [h for h in hits if overlap_count(question, _blob(h)) >= 2]


def should_refuse_expired(question: str, hits: list[Hit]) -> bool:
    useful = useful_hits(question, hits)
    if not useful:
        return False
    if useful[0].expired:
        return True
    return all(h.expired for h in useful)


def extract_from(hits: list[Hit], n: int = 3) -> tuple[str, list[str]]:
    top = [h for h in hits if not h.expired][:n] or hits[:n]
    cites = [h.chunk.id for h in top]
    parts = [f"根据《{h.chunk.title}》/{h.chunk.heading}：{h.chunk.text}" for h in top]
    return "\n\n".join(parts), cites


def _refuse(reason: str, steps: list[TraceStep], hits: list[Hit], mode: str, detail: str = "") -> Answer:
    text = "现有资料已过期，无法作为现行依据。" if reason == "expired" else "现有资料不足以回答该问题。"
    if detail:
        text = f"{text} {detail}"
    return Answer(text=text, refused=True, refuse_reason=reason, mode=mode, steps=steps, hits=hits)


def finalize_answer(
    question: str,
    text: str,
    cites: list[str],
    seen: dict[str, Hit],
    steps: list[TraceStep],
    fallback: list[Hit],
    mode: str,
) -> Answer:
    pool = list(seen.values()) or fallback
    if should_refuse_expired(question, pool):
        return _refuse("expired", steps, pool, mode)

    cited = [seen[c] for c in cites if c in seen]
    live = [h for h in cited if not h.expired]
    if cited and not live:
        return _refuse("expired", steps, pool, mode)
    if not live:
        return _refuse("no_evidence", steps, pool, mode)

    out_text = text.strip()
    out_cites = [h.chunk.id for h in live]
    if token_groundedness(out_text, live) < S.ground_min:
        out_text, out_cites = extract_from(live)
        steps = steps + [TraceStep(tool="ground", payload={"reason": "low_overlap"})]
    else:
        clipped = constrain_to_evidence(out_text, live)
        if not clipped:
            out_text, out_cites = extract_from(live)
            steps = steps + [TraceStep(tool="ground", payload={"reason": "no_supported_claim"})]
        elif clipped != out_text:
            out_text = clipped
            steps = steps + [TraceStep(tool="ground", payload={"reason": "clip_unsupported"})]
    return Answer(text=out_text, citations=out_cites, mode=mode, steps=steps, hits=pool)


def _extractive(question: str, user: User, index: Index, llm: LLM) -> Answer:
    hits = retrieve(question, user, index, llm=llm)
    steps = [TraceStep(tool="search", payload={"query": question}, observation=_hits_obs(hits))]
    useful = useful_hits(question, hits)
    if not useful:
        return _refuse("no_evidence", steps, hits, "extractive")
    if should_refuse_expired(question, useful):
        return _refuse("expired", steps, hits, "extractive")
    live = [h for h in useful if not h.expired]
    text, cites = extract_from(live)
    return Answer(text=text, citations=cites, mode="extractive", steps=steps, hits=hits)


def run_agent(question: str, user: User, index: Index, llm: LLM | None = None) -> Answer:
    t0 = time.perf_counter()
    llm = llm or LLM()
    if not llm.can_chat:
        ans = _extractive(question, user, index, llm)
    else:
        ans = _loop(question, user, index, llm)
        if ans.refused and ans.refuse_reason == "no_evidence":
            ext = _extractive(question, user, index, llm)
            if not ext.refused:
                ext.mode = "extractive_fallback"
                ext.steps = ans.steps + [
                    TraceStep(tool="fallback", payload={"reason": "agent_no_evidence"})
                ] + ext.steps
                ans = ext
    ans.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return ans


def _loop(question: str, user: User, index: Index, llm: LLM) -> Answer:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"用户部门={user.dept} 角色={','.join(user.roles)}\n问题：{question}"},
    ]
    seen: dict[str, Hit] = {}
    steps: list[TraceStep] = []
    last_hits: list[Hit] = []

    for _ in range(S.agent_max_steps):
        raw = llm.chat(messages)
        act = parse_json_object(raw) or {"tool": "refuse", "reason": "no_evidence", "detail": "模型未返回合法 JSON"}
        tool = str(act.get("tool", ""))
        messages.append({"role": "assistant", "content": json.dumps(act, ensure_ascii=False)})

        if tool == "search":
            query = str(act.get("query") or question)
            hits = retrieve(query, user, index, llm=llm)
            last_hits = hits
            for h in hits:
                seen[h.chunk.id] = h
            obs = _hits_obs(hits)
            steps.append(TraceStep(tool="search", payload={"query": query}, observation=obs))
            messages.append({"role": "user", "content": obs})
            continue

        if tool == "read":
            cid = str(act.get("chunk_id", ""))
            chunk = index.parent_of(cid)
            if chunk is None or not user.can_read(chunk):
                obs = "无法读取该块（不存在或无权限）。"
            else:
                seen[chunk.id] = seen.get(chunk.id) or Hit(chunk=chunk, score=0.0, expired=chunk.expired)
                obs = f"{chunk.id} 《{chunk.title}》/{chunk.heading}\n{chunk.parent_text}"
            steps.append(TraceStep(tool="read", payload={"chunk_id": cid}, observation=obs))
            messages.append({"role": "user", "content": obs})
            continue

        if tool == "answer":
            cites = [c for c in act.get("citations") or [] if isinstance(c, str) and c in seen]
            return finalize_answer(
                question,
                str(act.get("text") or ""),
                cites,
                seen,
                steps + [TraceStep(tool="answer", payload=act)],
                last_hits,
                "agent",
            )

        reason = act.get("reason") if act.get("reason") in ("no_evidence", "expired") else "no_evidence"
        return _refuse(
            reason,
            steps + [TraceStep(tool="refuse", payload=act)],
            list(seen.values()) or last_hits,
            "agent",
            str(act.get("detail") or ""),
        )

    return _refuse("no_evidence", steps, list(seen.values()) or last_hits, "agent")
