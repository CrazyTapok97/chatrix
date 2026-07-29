import asyncio
import logging
import random
import re

from aiogram.types import BufferedInputFile, Message

from config import (
    AUTO_CONTENT_ENABLED,
    AUTO_CONTENT_INTERVAL_MESSAGES,
    AUTO_CONTENT_MEME_WEIGHT,
)
from utils.demotivator import make_demotivator
from utils.history import BLACKLIST, get_history, get_two_random_messages
from utils.meme_gen import create_classic_meme
from utils.meme_storage import get_random_meme


logger = logging.getLogger(__name__)

_render_lock = asyncio.Lock()


def _is_blacklisted(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in BLACKLIST)

def _clean_meme_text(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text or text.startswith("/") or "http" in text.lower() or _is_blacklisted(text):
        return ""
    words = text.split()
    if len(words) < 2:
        return ""
    return " ".join(words[:14])


def _pick_meme_text(chat_id: int) -> str:
    messages = list(get_history(chat_id, limit=150))
    random.shuffle(messages)
    for item in messages:
        text = _clean_meme_text(item.get("t", ""))
        if text:
            return text
    return ""


async def _render_meme(file_path: str, text: str) -> bytes:
    return await asyncio.to_thread(create_classic_meme, file_path, text)


async def _render_demotivator(file_path: str, title: str, subtitle: str) -> bytes:
    def render() -> bytes:
        with open(file_path, "rb") as f:
            return make_demotivator(f.read(), title, subtitle)

    return await asyncio.to_thread(render)


def get_auto_content_status(chat_id: int) -> dict:
    history_count = len(get_history(chat_id))
    remainder = history_count % AUTO_CONTENT_INTERVAL_MESSAGES
    return {
        "enabled": AUTO_CONTENT_ENABLED,
        "history_count": history_count,
        "interval_messages": AUTO_CONTENT_INTERVAL_MESSAGES,
        "messages_until_next": AUTO_CONTENT_INTERVAL_MESSAGES - remainder,
    }


def _is_auto_content_message(history_count: int) -> bool:
    return (
        history_count > 0
        and history_count % AUTO_CONTENT_INTERVAL_MESSAGES == 0
    )


async def maybe_send_auto_content(
    message: Message,
    *,
    force: bool = False,
    force_type: str | None = None,
    history_count: int | None = None,
) -> bool:
    """Публикует мем или демотиватор на каждом N-м сообщении."""
    if not AUTO_CONTENT_ENABLED or message.chat.type == "private":
        return False
    if message.from_user and message.from_user.is_bot:
        return False
    if history_count is None:
        history_count = len(get_history(message.chat.id))
    if not force and not _is_auto_content_message(history_count):
        return False

    template = get_random_meme()
    if not template:
        return False

    _, file_path, _, _ = template
    try:
        async with _render_lock:
            make_meme = (
                force_type == "meme"
                or (
                    force_type != "demot"
                    and random.randint(1, 100) <= AUTO_CONTENT_MEME_WEIGHT
                )
            )
            if make_meme:
                text = _pick_meme_text(message.chat.id)
                if not text:
                    return False
                image = await _render_meme(file_path, text)
                filename = "auto_meme.jpg"
            else:
                title, subtitle = get_two_random_messages(message.chat.id)
                image = await _render_demotivator(file_path, title, subtitle)
                filename = "auto_demotivator.png"

        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=BufferedInputFile(image, filename=filename),
            business_connection_id=message.business_connection_id,
        )
        logger.info("Auto content sent to chat %s: %s", message.chat.id, filename)
        return True
    except Exception as e:
        logger.exception("Auto content failed for chat %s: %s", message.chat.id, e)
        return False
