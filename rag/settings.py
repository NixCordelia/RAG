from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)


def warn_missing_env() -> None:
    """CLI 提示：改 .env.example 不会生效。"""
    if not ENV_PATH.exists():
        example = ROOT / ".env.example"
        hint = f"复制 {example.name} 为 .env" if example.exists() else "新建 .env"
        print(f"未找到 .env（已加入 .gitignore，侧边栏/Git 里可能看不见）。{hint} 后再改；改 example 不会生效。")
    warn_gateway_model()


def _warn_pair(url: str, model: str, label: str) -> None:
    u, m = url.lower(), model.lower()
    if "deepseek.com" in u and (m.startswith("gpt") or m.startswith("o1") or "4o" in m or m.startswith("chatgpt")):
        print(
            f"警告：网关是 DeepSeek，但 {label}={model}。"
            "请改成 deepseek-v4-pro / deepseek-v4-flash / deepseek-chat，否则容易 HTTP 400。"
        )
    if "api.openai.com" in u and "deepseek" in m:
        print(f"警告：网关是 OpenAI，但 {label}={model}，请求会被拒绝。")


def warn_gateway_model() -> None:
    if S.api_key:
        _warn_pair(S.base_url, S.chat_model, "CHAT_MODEL")
    if S.eval_api_key:
        _warn_pair(S.eval_base_url, S.eval_chat_model, "EVAL_CHAT_MODEL")


@dataclass(frozen=True)
class Settings:
    corpus_dir: Path = ROOT / "data" / "corpus"
    index_dir: Path = ROOT / "data" / "index"
    gold_path: Path = ROOT / "data" / "goldenset.jsonl"
    gold_paraphrase_path: Path = ROOT / "data" / "goldenset_paraphrase.jsonl"
    traces_dir: Path = ROOT / "data" / "traces"
    eval_dir: Path = ROOT / "data" / "eval"

    api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    embed_backend: str = os.getenv("EMBED_BACKEND", "auto").lower()

    eval_api_key: str = (os.getenv("EVAL_API_KEY") or os.getenv("OPENAI_API_KEY", "")).strip()
    eval_base_url: str = (os.getenv("EVAL_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
    eval_chat_model: str = (os.getenv("EVAL_CHAT_MODEL") or os.getenv("CHAT_MODEL") or "gpt-4o-mini").strip()

    child_chars: int = 500
    child_overlap: int = 80
    pack_chars: int = 220
    chunk_strategy: str = os.getenv("CHUNK_STRATEGY", "section")
    retrieve_k: int = int(os.getenv("RETRIEVE_K", "8"))
    retrieve_doc_k: int = int(os.getenv("RETRIEVE_DOC_K", "5"))
    score_rel: float = float(os.getenv("SCORE_REL", "0.58"))
    ground_min: float = float(os.getenv("GROUND_MIN", "0.4"))
    rrf_k: int = 60
    dense_weight: float = 0.6
    agent_max_steps: int = 4
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))

    def embed_kind(self) -> str:
        b = self.embed_backend
        if b in ("hash", "m3e", "openai"):
            return b
        if self.api_key:
            return "openai"
        return "hash"

    def can_judge(self) -> bool:
        return bool(self.eval_api_key)

    def m3e_model(self) -> str:
        m = self.embed_model
        if not m or m.startswith("text-embedding"):
            return "moka-ai/m3e-small"
        return m


S = Settings()
