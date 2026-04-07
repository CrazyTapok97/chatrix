"""
Управление настройками чатов (хранятся в data/chat_settings.json)
"""

import json
import os
import asyncio
from typing import Literal

from config import SETTINGS_FILE, DEFAULT_ACCESS

_lock = asyncio.Lock()

AccessMode = Literal["all", "admin"]


def _load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def get_settings(chat_id: int) -> dict:
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {"access": DEFAULT_ACCESS}
            _save(data)
        return data[key]


async def set_access(chat_id: int, mode: AccessMode):
    async with _lock:
        data = _load()
        key = str(chat_id)
        if key not in data:
            data[key] = {}
        data[key]["access"] = mode
        _save(data)


async def get_access(chat_id: int) -> AccessMode:
    s = await get_settings(chat_id)
    return s.get("access", DEFAULT_ACCESS)
