from __future__ import annotations

from rag.models import User

PRESETS: dict[str, User] = {
    "engineer": User(user_id="u-eng", dept="engineering", roles=["engineer"]),
    "ops": User(user_id="u-ops", dept="ops", roles=["ops"]),
    "hr": User(user_id="u-hr", dept="hr", roles=["hr"]),
    "intern": User(user_id="u-intern", dept="engineering", roles=["intern"]),
}


def parse_user(name: str) -> User:
    key = (name or "engineer").strip().lower()
    if key in PRESETS:
        return PRESETS[key]
    return User(user_id=key, dept=key, roles=[key])
