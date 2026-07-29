import asyncio
import logging
import random

from aiogram.types import Message

from utils.ai import _ask

logger = logging.getLogger(__name__)

REACTIONS_BY_MOOD = {
    "funny":    ["😂", "🤣", "😁", "😆", "🤪", "🎉", "💀", "🤡", "😝"],
    "love":     ["❤️", "🥰", "😍", "😘", "💋", "🫶", "❤️‍🔥", "💯"],
    "sad":      ["😢", "😭", "🥺", "😔", "💔", "😓"],
    "angry":    ["😡", "🤬", "💢", "😤", "😾"],
    "surprise": ["😮", "🤯", "😱", "😲", "👀"],
    "cool":     ["😎", "🔥", "💯", "⚡", "🤙", "💪", "🚀", "🎯"],
    "agree":    ["👍", "🙌", "👏", "🤝", "🙏"],
    "disagree": ["👎", "🤦", "🤷", "😒", "🙄"],
    "think":    ["🤔", "🧐", "💭", "🤨"],
    "cringe":   ["😬", "😅", "🙈", "😳"],
    "wow":      ["🤩", "🙌", "🎊", "💫", "🥳"],
    "party":    ["🎉", "🥳", "🎊", "🎈"],
    "random":   ["💅", "🪄", "🎭", "🎲", "🧸", "🦄", "🌻"],
}

ALL_REACTIONS = [e for emojis in REACTIONS_BY_MOOD.values() for e in emojis]


async def send_ai_reaction(message, text: str, chance: float = 0.3):
    if random.random() > chance:
        return
    try:
        moods = list(REACTIONS_BY_MOOD.keys())
        prompt = (
            f"Определи настроение этого сообщения одним словом из списка: {', '.join(moods)}.\n"
            f"Сообщение: {text[:150]}\n"
            f"Ответь ТОЛЬКО одним словом из списка, без пояснений."
        )
        res = await _ask(prompt, max_tokens=10)
        mood = res.strip().lower().split()[0] if res else ""
        pool = REACTIONS_BY_MOOD.get(mood, ALL_REACTIONS)
        emoji = random.choice(pool)
        if random.random() < 0.35:
            emoji = "🍓"
        await message.bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[{"type": "emoji", "emoji": emoji}]
        )
    except Exception as e:
        logger.debug(f"[REACTION] {e}")