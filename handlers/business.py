"""
Хэндлеры для работы с Telegram Business (Secretary Mode).
Реализует вежливое поведение: бот уступает очередь ответа владельцу.
"""

import logging
import re
import asyncio
import time
import base64
import os
from aiogram import Router, F
from aiogram.types import BusinessConnection, Message, BusinessMessagesDeleted
from aiogram.filters import Command
from utils.ai import gen_business_reply
import json, random
from utils import business_state
from utils.history import add_message, add_photo, add_media
from config import DISABLE_AUTO_REPLY
from handlers.native_features import dispatch_business_command

logger = logging.getLogger(__name__)

router = Router()

@router.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    """Отслеживает подключение/отключение бота к бизнес-аккаунту."""
    status = "ПОДКЛЮЧЕН" if connection.is_enabled else "ОТКЛЮЧЕН"
    can_reply = "Разрешено" if connection.can_reply else "Запрещено"
    
    business_state.register_connection(connection.id, connection.user.id)
    
    logger.info(
        f"Бизнес-связь: {status}. "
        f"Пользователь: {connection.user.id} ({connection.user.full_name}). "
        f"Ответы от имени: {can_reply}."
    )

@router.business_message()
async def handle_business_message(message: Message):
    """Обрабатывает входящие и ИСХОДЯЩИЕ сообщения в бизнес-аккаунте."""
    content = message.text or message.caption or ""
    
    if message.photo:
        await add_photo(message.chat.id, message.photo[-1].file_id)
    if message.animation:
        await add_media(message.chat.id, message.animation.file_id, "gif")
    if message.video:
        await add_media(message.chat.id, message.video.file_id, "video")

    if not content and not message.photo:
        return

    if content.startswith("/") and await dispatch_business_command(message):
        return

    if content and re.match(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[GgCcHhRrTt]", content.strip()):
        logger.info(f"Обнаружена команда в бизнес-чате: {content[:10]}. Бизнес-логика пропущена.")
        return

    if content:
        username = message.from_user.username or message.from_user.first_name or "?"
        await add_message(message.chat.id, username, content)

    if message.chat.type != "private":
        return

    conn_id = message.business_connection_id
    owner_id = business_state.get_owner_id(conn_id)
    
    KNOWN_OWNERS = [892133524]
    CHATRIX_BOT_ID = 8727078930
    
    is_owner = False
    if message.from_user.id in KNOWN_OWNERS:
        is_owner = True
    elif owner_id and message.from_user.id == owner_id:
        is_owner = True
    elif message.chat.type == "private" and message.from_user.id != message.chat.id:
        is_owner = True

    if is_owner and message.chat.id != CHATRIX_BOT_ID:
        business_state.update_activity(message.from_user.id, message.chat.id)
        return

    if message.from_user.is_bot:
        logger.debug(f"Сообщение от бота {message.from_user.id} ({message.from_user.full_name}). Игнорируем.")
        return

    if DISABLE_AUTO_REPLY:
        return

    try:
        image_url = None
        if message.photo:
            try:
                file = await message.bot.get_file(message.photo[-1].file_id)
                os.makedirs("data/temp", exist_ok=True)
                tmp_path = f"data/temp/biz_{message.photo[-1].file_id}.jpg"
                await message.bot.download_file(file.file_path, tmp_path)
                with open(tmp_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                    image_url = f"data:image/jpeg;base64,{img_b64}"
                if os.path.exists(tmp_path): os.remove(tmp_path)
            except Exception as e:
                logger.error(f"Vision failed in business: {e}")

        reply_text = await gen_business_reply(message.from_user.full_name, content, image_url=image_url, chat_id=message.chat.id)
        if reply_text and not reply_text.startswith("❌"):
            if message.chat.type == "private":
                reply_text += " (ai)"

            await message.bot.send_message(
                chat_id=message.chat.id,
                text=reply_text,
                business_connection_id=message.business_connection_id
            )
            logger.info("[BUSINESS] %s: %s", message.from_user.full_name, reply_text[:80])
            sticker_packs_path = "data/sticker_packs.json"
            if os.path.exists(sticker_packs_path):
                try:
                    with open(sticker_packs_path, "r", encoding="utf-8") as f:
                        packs_data = json.load(f)
                    pack_names = packs_data.get("sticker_sets", [])
                    sticker_chance = 0.1
                    style_path = "data/crazybot_chat_settings.json"
                    if os.path.exists(style_path):
                        with open(style_path, "r", encoding="utf-8") as f:
                            style_data = json.load(f)
                        chat_style = style_data.get(str(message.chat.id), {})
                        if isinstance(chat_style, dict):
                            sticker_chance = float(chat_style.get("sticker_chance", sticker_chance))
                    if pack_names and random.random() < sticker_chance:
                        pack = random.choice(pack_names)
                        sticker_set = await message.bot.get_sticker_set(pack)
                        if sticker_set and sticker_set.stickers:
                            sticker = random.choice(sticker_set.stickers)
                            await message.bot.send_sticker(
                                chat_id=message.chat.id,
                                sticker=sticker.file_id,
                                business_connection_id=message.business_connection_id
                            )
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Ошибка в обработчике бизнес-сообщений: {e}")

@router.edited_business_message()
async def handle_edited_business_message(message: Message):
    """Обновляет активность при редактировании сообщения владельцем."""
    owner_id = business_state.get_owner_id(message.business_connection_id)
    if owner_id and message.from_user.id == owner_id:
        business_state.update_activity(owner_id, message.chat.id)
        logger.info(f"Владелец отредактировал сообщение в {message.chat.id}. Активность обновлена.")

@router.deleted_business_messages()
async def handle_deleted_business_messages(deleted: BusinessMessagesDeleted):
    logger.info(f"Удалено {len(deleted.message_ids)} сообщений в бизнес-чате {deleted.chat.id}")

@router.message(Command(re.compile(r"bizChat(\d+)")))
async def handle_business_deep_link(message: Message):
    match = re.search(r"bizChat(\d+)", message.text)
    if match:
        chat_id = match.group(1)
        await message.reply(
            f"🛠 <b>Управление секретарем</b>\n\n"
            f"Чат: <code>{chat_id}</code>\n"
            f"Я отвечаю мгновенно, используя адаптивный AI. Если вы начнете отвечать сами, я обновлю статус вашей активности.",
            parse_mode="HTML"
        )
