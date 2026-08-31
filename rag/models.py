from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from rag.text import is_expired

Role = str
RetrieveMode = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]
RefuseReason = Literal["no_evidence", "expired"]


@dataclass
class User:
    user_id: str
    dept: str
    roles: list[str]

    def can_read(self, chunk: Chunk) -> bool:
        if "admin" in self.roles or "all" in chunk.acl:
            return True
        return any(r in chunk.acl for r in self.roles)


@dataclass
class Chunk:
    id: str
    doc_id: str
    title: str
    heading: str
    text: str
    parent_text: str
    dept: str
    acl: list[str]
    classification: str
    version: str
    expires: str | None
    source: str

    @property
    def expired(self) -> bool:
        return is_expired(self.expires)

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "title": self.title,
            "heading": self.heading,
            "text": self.text,
            "classification": self.classification,
            "version": self.version,
            "expires": self.expires,
            "expired": self.expired,
        }


@dataclass
class Hit:
    chunk: Chunk
    score: float
    expired: bool


@dataclass
class TraceStep:
    tool: str
    payload: dict[str, Any]
    observation: str | None = None


@dataclass
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)
    refused: bool = False
    refuse_reason: str | None = None
    mode: str = "agent"
    steps: list[TraceStep] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "citations": self.citations,
            "refused": self.refused,
            "refuse_reason": self.refuse_reason,
            "mode": self.mode,
            "latency_ms": self.latency_ms,
            "steps": [{"tool": s.tool, "payload": s.payload, "observation": s.observation} for s in self.steps],
            "hits": [
                {
                    "id": h.chunk.id,
                    "doc_id": h.chunk.doc_id,
                    "title": h.chunk.title,
                    "heading": h.chunk.heading,
                    "score": round(h.score, 4),
                    "expired": h.expired,
                    "text": h.chunk.text[:240],
                }
                for h in self.hits
            ],
        }
