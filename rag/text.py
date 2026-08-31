from __future__ import annotations

import re
from datetime import date
from typing import Any

FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")
STOP = {
    "以及",
    "如果",
    "可以",
    "应当",
    "进行",
    "使用",
    "通过",
    "什么",
    "怎么",
    "如何",
    "是否",
    "还是",
    "或者",
    "不是",
    "没有",
    "一个",
    "这个",
    "为什么",
    "今天",
    "现在",
}


def parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    m = FM_RE.match(raw)
    if not m:
        return {}, raw.strip()
    meta: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
        elif val in ("null", "None", "~", ""):
            meta[key] = None
        else:
            meta[key] = val.strip('"').strip("'")
    return meta, m.group(2).strip()


def tokenize(text: str) -> list[str]:
    toks: list[str] = []
    for m in TOKEN_RE.finditer(text or ""):
        piece = m.group()
        if piece.isascii():
            low = piece.lower()
            if len(low) >= 2 and low not in STOP:
                toks.append(low)
            continue
        if len(piece) < 2:
            continue
        for i in range(len(piece) - 1):
            bg = piece[i : i + 2]
            if bg not in STOP:
                toks.append(bg)
    return toks


def overlap_count(query: str, doc: str) -> int:
    return len(set(tokenize(query)) & set(tokenize(doc)))


def split_sections(body: str) -> list[tuple[str, str]]:
    heading = "正文"
    buf: list[str] = []
    sections: list[tuple[str, str]] = []
    for line in body.splitlines():
        if re.match(r"^#{1,3} ", line):
            text = "\n".join(buf).strip()
            if text:
                sections.append((heading, text))
            heading = re.sub(r"^#{1,3} ", "", line).strip()
            buf = []
        else:
            buf.append(line)
    text = "\n".join(buf).strip()
    if text:
        sections.append((heading, text))
    return sections or [("正文", body.strip())]


SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def pack_units(units: list[str], size: int) -> list[str]:
    packs: list[str] = []
    buf = ""
    for u in units:
        if buf and len(buf) + 1 + len(u) > size:
            packs.append(buf)
            buf = u
        else:
            buf = f"{buf} {u}".strip() if buf else u
    if buf:
        packs.append(buf)
    return packs


def child_parts(section: str, strategy: str, window: int, overlap: int, pack: int) -> list[tuple[str, str]]:
    """Return (child, parent). parent is the heading section except sent_only."""
    if strategy == "sent_only":
        return [(s, s) for s in split_sentences(section)]
    if strategy == "sent_pack":
        return [(p, section) for p in pack_units(split_sentences(section), pack)]
    return [(w, section) for w in windows(section, window, overlap)]


def windows(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text]
    out: list[str] = []
    step = max(size - overlap, 1)
    i = 0
    while i < len(text):
        out.append(text[i : i + size])
        i += step
    return out


def is_expired(expires: str | None, today: date | None = None) -> bool:
    if not expires:
        return False
    return date.fromisoformat(expires) < (today or date.today())
