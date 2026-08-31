from __future__ import annotations

import json
from datetime import datetime, timezone

from rag.models import Answer
from rag.settings import S


def write_ask(user: str, question: str, ans: Answer) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "question": question,
        **ans.to_dict(),
    }
    S.traces_dir.mkdir(parents=True, exist_ok=True)
    with (S.traces_dir / "ask.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
