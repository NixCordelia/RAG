from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from rag.agent import run_agent
from rag.index import index_exists, load_index
from rag.llm import LLM
from rag.settings import S, warn_gateway_model
from rag.trace import write_ask
from rag.users import PRESETS, parse_user

_llm: LLM | None = None
_index = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _llm, _index
    warn_gateway_model()
    _llm = LLM()
    _index = load_index() if index_exists() else None
    yield


app = FastAPI(title="WikiRAG", version="0.1.0", lifespan=lifespan)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    user: str = "engineer"


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    meta = {}
    p = S.index_dir / "meta.json"
    if p.exists():
        meta = json.loads(p.read_text(encoding="utf-8"))
    return {
        "ok": _index is not None,
        "n_chunks": len(_index.chunks) if _index else 0,
        "index": meta,
        "embed": meta.get("backend") or (_llm.embed_kind if _llm else None),
        "chat": bool(_llm and _llm.can_chat),
        "users": list(PRESETS),
    }


@app.post("/api/ask")
def ask(body: AskIn) -> dict:
    if _index is None or _llm is None:
        raise HTTPException(status_code=503, detail="索引不存在，请先运行 python -m rag ingest")
    user = parse_user(body.user)
    ans = run_agent(body.question, user, _index, _llm)
    write_ask(body.user, body.question, ans)
    return ans.to_dict()


def serve() -> None:
    import uvicorn

    uvicorn.run("rag.app:app", host=S.host, port=S.port, reload=False)
