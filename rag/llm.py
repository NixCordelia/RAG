from __future__ import annotations

import json
from typing import Any

import httpx
import numpy as np

from rag.embed import hashed_embed, l2_normalize, m3e_embed
from rag.settings import S


class LLM:
    def __init__(self) -> None:
        self.api_key = S.api_key
        self.base_url = S.base_url
        self.chat_model = S.chat_model
        self.embed_model = S.embed_model
        self._client = httpx.Client(timeout=60.0)
        self.tokens = 0

    @property
    def can_chat(self) -> bool:
        return bool(self.api_key)

    @property
    def embed_kind(self) -> str:
        return S.embed_kind()

    @property
    def can_embed(self) -> bool:
        return self.embed_kind in ("openai", "m3e")

    def embed(self, texts: list[str]) -> np.ndarray:
        kind = self.embed_kind
        if not texts:
            if kind == "m3e":
                dim = 768 if "base" in S.m3e_model().lower() else 512
            else:
                from rag.embed import HASH_DIM

                dim = HASH_DIM
            return np.zeros((0, dim), dtype=np.float32)
        if kind == "hash":
            return hashed_embed(texts)
        if kind == "m3e":
            return l2_normalize(m3e_embed(texts, S.m3e_model()))
        vecs: list[list[float]] = []
        for i in range(0, len(texts), 32):
            batch = texts[i : i + 32]
            data = self._post(
                "/embeddings",
                {"model": self.embed_model, "input": batch},
            )
            by_idx = {item["index"]: item["embedding"] for item in data["data"]}
            vecs.extend(by_idx[j] for j in range(len(batch)))
        return l2_normalize(np.asarray(vecs, dtype=np.float32))

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        if not self.can_chat:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法调用聊天模型")
        data = self._post(
            "/chat/completions",
            {
                "model": self.chat_model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        usage = data.get("usage") or {}
        self.tokens += int(usage.get("total_tokens") or 0)
        return data["choices"][0]["message"]["content"].strip()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        r = self._client.post(f"{self.base_url}{path}", headers=headers, json=payload)
        if r.status_code >= 400:
            body = (r.text or "").replace("\n", " ")[:800]
            raise RuntimeError(
                f"Chat API {r.status_code} {self.base_url}{path} model={payload.get('model')}: {body}"
            )
        return r.json()


def parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
