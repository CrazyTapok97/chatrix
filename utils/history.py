"""
Хранение истории сообщений и фото чата.
"""

import json
import os
import asyncio
import random

HISTORY_FILE = "data/chat_history.json"
MAX_MESSAGES = 0  # 0 = без лимита
MAX_PHOTOS = 0    # 0 = без лимита

_lock = asyncio.Lock()


def _load() -> dict:
    if not os.path.exists(HISTORY_FILE):
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def add_message(chat_id: int, username: str, text: str):
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {"messages": [], "photos": []}
        # совместимость со старым форматом
        if isinstance(data[key], list):
            data[key] = {"messages": data[key], "photos": []}
        data[key]["messages"].append({"u": username, "t": text})
        _save(data)


async def add_photo(chat_id: int, file_id: str):
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {"messages": [], "photos": []}
        if isinstance(data[key], list):
            data[key] = {"messages": data[key], "photos": []}
        if file_id not in data[key]["photos"]:
            data[key]["photos"].append(file_id)
        _save(data)


def get_random_photo(chat_id: int) -> str | None:
    data = _load()
    key = str(chat_id)
    entry = data.get(key, {})
    if isinstance(entry, list):
        return None
    photos = entry.get("photos", [])
    return random.choice(photos) if photos else None


def get_history(chat_id: int, limit: int = 0) -> list[dict]:
    data = _load()
    key = str(chat_id)
    entry = data.get(key, {})
    if isinstance(entry, list):
        msgs = entry
    else:
        msgs = entry.get("messages", [])
    
    if limit and limit > 0:
        return msgs[-limit:]
    return msgs  # весь список без лимита


def format_history(chat_id: int, limit: int = 50000) -> str:
    msgs = get_history(chat_id, limit)
    if not msgs:
        return ""
    # Перемешиваем чтобы каждый раз AI видел разные сообщения первыми
    import random
    msgs = list(msgs)
    random.shuffle(msgs)
    return "\n".join(f"{m['u']}: {m['t']}" for m in msgs)


def get_random_message(chat_id: int) -> str | None:
    """Возвращает случайное сообщение из истории чата."""
    msgs = get_history(chat_id, limit=50000)
    if not msgs:
        return None
    return random.choice(msgs)["t"]


def get_two_random_messages(chat_id: int) -> tuple[str, str]:
    msgs = get_history(chat_id)  # все сообщения, без лимита
    if not msgs:
        return "ЖИЗНЬ", "она такая"

    def _clean(text: str, max_words: int) -> str:
        text = text.strip()
        for sep in ['.', '!', '?']:
            idx = text.find(sep)
            if 0 < idx < 80:
                return text[:idx + 1].strip()
        words = text.split()
        return " ".join(words[:max_words]) if len(words) > max_words else text

    # Фильтруем мусор
    filtered = [
        m for m in msgs
        if len(m["t"].split()) >= 2
        and not m["t"].startswith("/")
        and "http" not in m["t"]
        and len(m["t"]) <= 200
    ]

    if len(filtered) < 2:
        filtered = msgs

    picks = random.sample(filtered, 2)
    title    = _clean(picks[0]["t"], max_words=5).upper()
    subtitle = _clean(picks[1]["t"], max_words=8)
    return title, subtitle


def get_poll_data(chat_id: int) -> dict | None:
    """Возвращает случайный опрос из истории чата."""
    msgs = get_history(chat_id, limit=100)
    if len(msgs) < 5:
        return None
    picks = random.sample(msgs, 5)
    question = picks[0]["t"]
    options = [m["t"] for m in picks[1:5]]
    # Обрезаем если слишком длинные (Telegram лимит 100 символов)
    question = question[:100]
    options = [o[:100] for o in options]
    return {
        "question": question,
        "options": options,
        "is_quiz": False,
        "correct_option_id": 0,
    }