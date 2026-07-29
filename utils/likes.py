"""
Хранилище лайков/дизлайков для демотиваторов S g d ai.
Формат JSON:
{
  "message_id:chat_id": {
    "title": "...",
    "subtitle": "...",
    "likes": 0,
    "dislikes": 0,
    "voters": {"user_id": "up"/"down"}
  }
}
"""
from __future__ import annotations
import json
from pathlib import Path

LIKES_FILE = Path("data/likes.json")


def _load() -> dict:
    if not LIKES_FILE.exists():
        LIKES_FILE.parent.mkdir(parents=True, exist_ok=True)
        return {}
    try:
        return json.loads(LIKES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    LIKES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(message_id: int, chat_id: int) -> str:
    return f"{message_id}:{chat_id}"


def register_demot(message_id: int, chat_id: int, title: str, subtitle: str) -> None:
    """Регистрирует новый демотиватор с его текстом. Вызывается сразу после отправки."""
    data = _load()
    k = _key(message_id, chat_id)
    data[k] = {
        "title": title,
        "subtitle": subtitle,
        "likes": 0,
        "dislikes": 0,
        "voters": {},
    }
    _save(data)


def vote(message_id: int, chat_id: int, user_id: int, vote_type: str) -> dict:
    """
    Проголосовать. vote_type: 'up' или 'down'.
    Повторный голос снимает его.
    Возвращает {'likes', 'dislikes', 'my_vote'}.
    """
    data = _load()
    k = _key(message_id, chat_id)
    uid = str(user_id)

    entry = data.get(k)
    if not entry:
        return {"likes": 0, "dislikes": 0, "my_vote": None}

    prev = entry["voters"].get(uid)
    if prev == vote_type:
        del entry["voters"][uid]
        if vote_type == "up":
            entry["likes"] = max(0, entry["likes"] - 1)
        else:
            entry["dislikes"] = max(0, entry["dislikes"] - 1)
        my_vote = None
    else:
        if prev == "up":
            entry["likes"] = max(0, entry["likes"] - 1)
        elif prev == "down":
            entry["dislikes"] = max(0, entry["dislikes"] - 1)
        entry["voters"][uid] = vote_type
        if vote_type == "up":
            entry["likes"] += 1
        else:
            entry["dislikes"] += 1
        my_vote = vote_type

    _save(data)
    return {"likes": entry["likes"], "dislikes": entry["dislikes"], "my_vote": my_vote}


def top_examples(chat_id: int, limit: int = 5) -> list[dict]:
    """
    Топ демотиваторов по рейтингу для few-shot обучения промпта.
    Исключает демотиваторы с нулевым/отрицательным рейтингом.
    """
    data = _load()
    result = []
    for k, entry in data.items():
        _, cid = k.split(":", 1)
        if int(cid) != chat_id:
            continue
        score = entry["likes"] - entry["dislikes"]
        if score <= 0:
            continue
        result.append({
            "title": entry.get("title", ""),
            "subtitle": entry.get("subtitle", ""),
            "score": score,
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:limit]


def top(chat_id: int, limit: int = 5) -> list[dict]:
    """Топ для отображения (с message_id)."""
    data = _load()
    result = []
    for k, entry in data.items():
        mid, cid = k.split(":", 1)
        if int(cid) != chat_id:
            continue
        score = entry["likes"] - entry["dislikes"]
        result.append({
            "message_id": int(mid),
            "title": entry.get("title", ""),
            "subtitle": entry.get("subtitle", ""),
            "likes": entry["likes"],
            "dislikes": entry["dislikes"],
            "score": score,
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:limit]