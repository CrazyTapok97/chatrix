"""
Проверка прав доступа: admin или all.
"""

from aiogram.types import Message, ChatMemberAdministrator, ChatMemberOwner
from utils.settings_store import get_access


async def is_admin(message: Message) -> bool:
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False


async def can_use_commands(message: Message) -> bool:
    """Возвращает True если пользователь имеет право на команды в этом чате."""
    if message.chat.type == "private":
        return True
    access = await get_access(message.chat.id)
    if access == "all":
        return True
    return await is_admin(message)
