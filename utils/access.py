"""
Проверка прав доступа: admin или all.
"""

from aiogram.types import Message, ChatMemberAdministrator, ChatMemberOwner
from config import ADMIN_IDS
from utils.settings_store import get_access
from utils import business_state

async def is_admin(message: Message) -> bool:
    # 1. Если это бизнес-сообщение, проверяем является ли отправитель владельцем
    if message.business_connection_id:
        owner_id = business_state.get_owner_id(message.business_connection_id)
        if owner_id and message.from_user.id == owner_id:
            return True
        # Резервный список владельцев
        if message.from_user.id in ADMIN_IDS:
            return True

    # 2. Обычная проверка прав в группе
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        # Если бота нет в группе, он не может проверить права.
        # В этом случае, если это бизнес-чат, мы уже проверили владельца выше.
        # Для остальных возвращаем False.
        return False


async def can_use_commands(message: Message) -> bool:
    """Возвращает True если пользователь имеет право на команды в этом чате."""
    if message.chat.type == "private":
        return True
    access = await get_access(message.chat.id)
    if access == "all":
        return True
    return await is_admin(message)
