"""
Конфиг бота. Заполни переменные перед запуском.
"""

import os

# ─── Токены ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "YOUR_OPENROUTER_KEY_HERE")

# ─── Модели через OpenRouter (перебираются по очереди если 429) ───────────────
GEMINI_MODEL = "openai/gpt-oss-120b:free"  # основная

FALLBACK_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "minimax/minimax-m2.5:free",
]

# ─── Кулдауны отключены ───────────────────────────────────────────────────────
COOLDOWN_DEFAULT = 0
COOLDOWN_ADMIN   = 0
NO_COOLDOWN_CMDS = {"word", "word_len"}

# ─── Режимы доступа к командам ────────────────────────────────────────────────
ACCESS_MODES = ["all", "admin"]
DEFAULT_ACCESS = "all"

# ─── Путь к файлу настроек чатов ─────────────────────────────────────────────
SETTINGS_FILE = "data/chat_settings.json"

# ─── Мем-шаблоны ─────────────────────────────────────────────────────────────
MEM_TEMPLATES = [
    "Когда наконец пятница",
]
