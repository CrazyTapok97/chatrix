import json
import os
import tempfile
from pathlib import Path

SETTINGS_FILE = Path("data/crazybot_chat_settings.json")
DEFAULTS = {
    "prompt": "",
    "vision_prompt": "",
    "reply_every": 10,
    "sticker_chance": 0.5,
    "style_mode": "prompt",
}


def _load() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".chat_style_", dir=SETTINGS_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, SETTINGS_FILE)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def get_chat_settings(chat_id: int) -> dict:
    data = _load()
    result = dict(DEFAULTS)
    entry = data.get(str(chat_id), {})
    if isinstance(entry, dict):
        result.update(entry)
    return result


def normalize_setting(name: str, value: str):
    name = name.lower().strip()
    if name == "style":
        if not value.strip(): raise ValueError("Стиль не может быть пустым")
        return "prompt", value.strip()
    if name == "vstyle":
        if not value.strip(): raise ValueError("Vision-стиль не может быть пустым")
        return "vision_prompt", value.strip()
    if name == "group":
        return "reply_every", max(1, int(value))
    if name == "chance":
        return "sticker_chance", max(0.0, min(1.0, float(value)))
    if name == "mode":
        mode = value.lower().strip()
        if mode in {"mystyle", "rag"}:
            return "style_mode", "mystyle"
        if mode in {"prompt", "default"}:
            return "style_mode", "prompt"
        raise ValueError("Режим: default или mystyle")
    raise ValueError("Доступно: style, vstyle, group, chance, mode")


def update_chat_setting(chat_id: int, name: str, value: str):
    key, normalized = normalize_setting(name, value)
    data = _load()
    entry = data.setdefault(str(chat_id), {})
    if not isinstance(entry, dict):
        entry = data[str(chat_id)] = {}
    entry[key] = normalized
    _save(data)
    return key, normalized


def style_instruction(chat_id: int, vision: bool = False) -> str:
    settings = get_chat_settings(chat_id)
    if vision and settings.get("vision_prompt"):
        return str(settings["vision_prompt"])
    return str(settings.get("prompt", "") or "")