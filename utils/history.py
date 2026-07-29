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

BLACKLIST = [
    "рисую", "нарисуй", "нарисуйте", "рисую...",
    "анализируй", "анализирую", "проанализируй", "проанализирую", "проанализировать", "анализ...",
    "сгенерируй", "сгенерирую", "сгенерируйте",
]

_lock = asyncio.Lock()
_cache = None  # Внутриигровой кэш истории


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
        
    if not os.path.exists(HISTORY_FILE):
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        _cache = {}
        return _cache
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
            return _cache
    except Exception:
        _cache = {}
        return _cache


def _save(data: dict):
    global _cache
    _cache = data
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _is_blacklisted(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in BLACKLIST)

async def add_message(chat_id: int, username: str, text: str, reply_to_username: str = ""):
    if _is_blacklisted(text):
        return 0
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {"messages": [], "photos": []}
        if isinstance(data[key], list):
            data[key] = {"messages": data[key], "photos": []}
        msg = {"u": username, "t": text}
        if reply_to_username:
            msg["r"] = reply_to_username
        data[key]["messages"].append(msg)
        _save(data)
        return len(data[key]["messages"])


async def add_photo(chat_id: int, file_id: str):
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {"messages": [], "photos": [], "gifs": [], "videos": []}
        if isinstance(data[key], list):
            data[key] = {"messages": data[key], "photos": [], "gifs": [], "videos": []}
        if "gifs" not in data[key]: data[key]["gifs"] = []
        if "videos" not in data[key]: data[key]["videos"] = []
            
        if file_id not in data[key]["photos"]:
            data[key]["photos"].append(file_id)
        _save(data)


async def add_media(chat_id: int, file_id: str, media_type: str):
    """Сохраняет GIF или Видео."""
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {"messages": [], "photos": [], "gifs": [], "videos": []}
        if not isinstance(data[key], dict):
             data[key] = {"messages": [], "photos": [], "gifs": [], "videos": []}
        
        m_key = "gifs" if media_type == "gif" else "videos"
        if m_key not in data[key]: data[key][m_key] = []
        
        if file_id not in data[key][m_key]:
            data[key][m_key].append(file_id)
        _save(data)


def get_random_media(chat_id: int, media_type: str) -> str | None:
    data = _load()
    key = str(chat_id)
    entry = data.get(key, {})
    if not isinstance(entry, dict): return None
    m_key = "gifs" if media_type == "gif" else "videos"
    media = entry.get(m_key, [])
    return random.choice(media) if media else None


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


def _format_msg(m: dict) -> str:
    if m.get("r"):
        return f"{m['u']} > {m['r']}: {m['t']}"
    return f"{m['u']}: {m['t']}"


def format_history(chat_id: int, limit: int = 500, shuffle_past: bool = False, recent: int = 0) -> str:
    msgs_all = get_history(chat_id, limit)
    if not msgs_all:
        return ""
    msgs_all = [m for m in msgs_all if not _is_blacklisted(m.get("t", ""))]
    if not msgs_all:
        return ""

    if recent and recent > 0:
        chrono = list(msgs_all[-recent:])
        past = list(msgs_all[:-recent])
    else:
        chrono = []
        past = list(msgs_all)

    if shuffle_past and past:
        random.shuffle(past)

    lines = []
    if past:
        lines.append("---")
        lines.extend(_format_msg(m) for m in past)
    if chrono:
        lines.append("---")
        lines.extend(_format_msg(m) for m in chrono)
    return "\n".join(lines)


def get_random_message(chat_id: int) -> str | None:
    msgs = [m for m in get_history(chat_id, limit=50000) if not _is_blacklisted(m["t"])]
    if not msgs:
        return None
    return random.choice(msgs)["t"]


def get_two_random_messages(chat_id: int) -> tuple[str, str]:
    msgs = get_history(chat_id, limit=2000)
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

    filtered = [
        m for m in msgs
        if len(m["t"].split()) >= 2
        and not m["t"].startswith("/")
        and "http" not in m["t"]
        and len(m["t"]) <= 200
        and not _is_blacklisted(m["t"])
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
