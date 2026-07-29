"""
Прочие хэндлеры: /start, S h, сбор истории сообщений и фото.
Обеспечивает гарантированный отклик бота и правильную фильтрацию.
"""

import asyncio
import json
import logging
import re
import base64
import os
import random
import time
import uuid
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BufferedInputFile, FSInputFile
from PIL import Image

from utils.history import add_message, add_photo, add_media, format_history, get_history, get_random_message
from utils.ai import _ask, gen_smart_reply
from utils.chat_style import get_chat_settings, style_instruction
from config import ADMIN_IDS
from utils.settings_store import get_intelligence
from utils.access import can_use_commands, is_admin
from utils.meme_storage import add_meme, get_meme_by_id, update_file_id, get_memes, index_memes
from utils.meme_gen import create_classic_meme
from utils.auto_content import get_auto_content_status, maybe_send_auto_content
from utils.native_features import generate_image
from utils.demotivator import make_demotivator

# Контекст последних ответов бота для продолжения мысли
last_bot_reply: dict[int, str] = {}
last_bot_ctx: dict[int, dict] = {}
last_bot_msg_time: dict[int, float] = {}

# Кулдаун автодемотиваторов (чат → timestamp последнего)
_last_demot_time: dict[int, float] = {}
_DEMOT_COOLDOWN_SECONDS = 7200  # 2 часа
from utils.reactions import send_ai_reaction
from utils.name_cache import get_name as cached_get_name
from utils.intents import determine_tool, get_weather
from utils.native_features import web_search
from utils.antispam import is_ratelimited
from config import DISABLE_AUTO_REPLY, MEME_CACHE_CHAT_ID

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = """
🤖 <b>Chatrix</b> — генератор контента и умный собеседник

<b>💬 Как общаться:</b>
- Используй инлайн-режим: <code>@имя_бота текст</code> для создания мемов!
- В личных сообщениях я отвечаю на каждое 5-е сообщение.

<b>🎮 Команды генерации:</b>
<code>S g</code> — панель генерации
<code>S g m</code> — мем
<code>S g d</code> — демотиватор (реплай на фото)
<code>S g a</code> — анекдот
<code>S index</code> — индексация мемов (для админов)
<code>/addmeme</code> — добавить картинку в шаблоны

<b>🎭 Мафия:</b>
<code>/mafia</code> — создать лобби
<code>/join</code> — войти в игру
<code>/ready</code> — готов
<code>/helpmafia</code> — правила

<b>⚙️ Настройки:</b>
<code>S c</code> — настройки чата (только админы)
<code>S h</code> — помощь
""".strip()

START_TEXT = """
🤖 <b>Chatrix</b> — генератор контента и умный собеседник

<b>💬 Как общаться:</b>
- Введи <code>@имя_бота текст</code> в любом чате для создания мема!

Полный список команд: <code>S h</code>
""".strip()

# --- Системные команды ---

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply(f"Привет! 👋\n{START_TEXT}", parse_mode="HTML")

@router.message(F.text.startswith("GEN_MEME:"))
async def trigger_meme_generation(message: Message):
    """Перехват триггера и замена его на готовый мем."""
    content = message.text
    parts = content.split(":")
    if len(parts) < 3: return
    
    meme_id = int(parts[1])
    b64_text = parts[2]
    
    try:
        padding = '=' * (-len(b64_text) % 4)
        text = base64.urlsafe_b64decode(b64_text + padding).decode()
    except:
        text = ""

    meme = get_meme_by_id(meme_id)
    if not meme: return
        
    _, file_path, _, _ = meme
    
    try:
        meme_bytes = create_classic_meme(file_path, text or " ")
        photo = BufferedInputFile(meme_bytes, filename="meme.jpg")
        
        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            business_connection_id=message.business_connection_id
        )
    except Exception as e:
        logger.error(f"Meme Error: {e}")
        await message.reply("❌ Не удалось создать мем.")
        return

    try:
        await message.delete()
    except Exception as e:
        # В группах удаление сообщения пользователя требует прав администратора.
        logger.warning(f"Meme generated, but trigger message could not be deleted: {e}")

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Hh]$"))
@router.business_message(F.text.regexp(r"(?i)^[Ss]\s+[Hh]$"))
async def cmd_help(message: Message):
    await message.bot.send_message(
        chat_id=message.chat.id,
        text=HELP_TEXT,
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Ii][Nn][Dd][Ee][Xx]$"))
async def cmd_index_memes(message: Message):
    """Команда для индексации и загрузки шаблонов в Telegram для получения file_id."""
    if not await can_use_commands(message): return
    
    await message.reply("🔄 Начинаю индексацию мемов... это может занять время.")
    
    new_count, total_count = await index_memes()
    await message.answer(f"✅ Индексация БД: +{new_count} новых файлов. Всего в БД: {total_count}. Начинаю загрузку превью...")
    
    all_memes = get_memes(limit=5000)
    count = 0
    for meme_id, file_path, file_id, thumb_id in all_memes:
        if not file_id:
            try:
                photo = FSInputFile(file_path)
                sent = await message.answer_photo(photo, caption=f"Template #{meme_id}")
                file_id = sent.photo[-1].file_id
                update_file_id(meme_id, file_id)
                count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error uploading {file_path}: {e}")
                
    await message.answer(f"🏁 Индексация завершена. Загружено превью для новых шаблонов: {count}")


def _addmeme_source(message: Message):
    if message.photo or message.document:
        return message
    replied = message.reply_to_message
    if replied and (replied.photo or replied.document):
        return replied
    return None


def _image_extension(source: Message) -> str | None:
    if source.photo:
        return ".jpg"
    document = source.document
    if not document:
        return None
    mime = (document.mime_type or "").lower()
    extension = os.path.splitext(document.file_name or "")[1].lower()
    if mime == "image/png" or extension == ".png":
        return ".png"
    if mime in {"image/jpeg", "image/jpg"} or extension in {".jpg", ".jpeg"}:
        return ".jpg"
    if mime == "image/webp" or extension == ".webp":
        return ".webp"
    return None


@router.message(Command("addmeme"))
async def cmd_add_meme(message: Message):
    """Сохраняет фото как новый шаблон и сразу регистрирует Telegram file_id."""
    if not await can_use_commands(message):
        await message.reply("⛔ Добавление шаблонов недоступно.")
        return

    source = _addmeme_source(message)
    extension = _image_extension(source) if source else None
    if not source or not extension:
        await message.reply(
            "🖼 <b>Как добавить шаблон</b>\n\n"
            "• отправь фото с подписью <code>/addmeme</code>\n"
            "• или ответь командой <code>/addmeme</code> на фото\n\n"
            "Поддерживаются JPG, PNG и WEBP.",
            parse_mode="HTML",
        )
        return

    media = source.photo[-1] if source.photo else source.document
    upload_dir = os.path.join("memes", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{extension}"
    relative_path = os.path.join(upload_dir, filename).replace("\\", "/")

    cache_message = None
    try:
        await message.bot.download(media, destination=relative_path)

        if extension == ".webp":
            png_path = os.path.splitext(relative_path)[0] + ".png"
            with Image.open(relative_path) as image:
                image.convert("RGB").save(png_path, format="PNG")
            os.remove(relative_path)
            relative_path = png_path
            filename = os.path.basename(png_path)

        if source.photo:
            photo_file_id = source.photo[-1].file_id
        else:
            cache_message = await message.bot.send_photo(
                chat_id=MEME_CACHE_CHAT_ID,
                photo=FSInputFile(relative_path),
            )
            photo_file_id = cache_message.photo[-1].file_id

        meme_id = add_meme(relative_path, photo_file_id)
        await message.reply(
            "✅ <b>Шаблон добавлен</b>\n\n"
            f"ID: <code>{meme_id}</code>\n"
            f"Файл: <code>{filename}</code>\n\n"
            "Он уже доступен в inline-галерее.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception(f"Could not add meme: {e}")
        try:
            if os.path.exists(relative_path):
                os.remove(relative_path)
        except OSError:
            pass
        await message.reply("❌ Не удалось сохранить шаблон.")
    finally:
        if cache_message:
            try:
                await cache_message.delete()
            except Exception:
                pass


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "нет"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {secs} сек"
    return f"{secs} сек"


@router.message(Command("autostatus"))
async def cmd_auto_content_status(message: Message):
    if message.chat.type == "private":
        await message.reply("Проверять автоконтент нужно в группе.")
        return
    if not await is_admin(message):
        await message.reply("⛔ Команда доступна администраторам группы.")
        return

    status = get_auto_content_status(message.chat.id)
    await message.reply(
        "⚙️ <b>Автоконтент</b>\n\n"
        f"Система включена: <b>{'да' if status['enabled'] else 'нет'}</b>\n"
        f"Сообщений в chat_history.json: <b>{status['history_count']}</b>\n"
        f"Публикация: <b>каждое {status['interval_messages']}-е сообщение</b>\n"
        f"До следующей публикации: <b>{status['messages_until_next']}</b>\n"
        "Формат: <b>50% мем / 50% демотиватор</b>\n\n"
        "Проверка: <code>/testauto meme</code> или <code>/testauto demot</code>",
        parse_mode="HTML",
    )


@router.message(Command("testauto"))
async def cmd_test_auto_content(message: Message):
    if message.chat.type == "private":
        await message.reply("Тестировать автоконтент нужно в группе.")
        return
    if not await is_admin(message):
        await message.reply("⛔ Команда доступна администраторам группы.")
        return

    parts = (message.text or "").split(maxsplit=1)
    requested = parts[1].strip().lower() if len(parts) > 1 else ""
    aliases = {
        "meme": "meme",
        "мем": "meme",
        "demot": "demot",
        "демот": "demot",
        "демотиватор": "demot",
    }
    force_type = aliases.get(requested)
    if requested and not force_type:
        await message.reply("Используй: /testauto meme или /testauto demot")
        return

    sent = await maybe_send_auto_content(
        message,
        force=True,
        force_type=force_type,
    )
    if not sent:
        status = get_auto_content_status(message.chat.id)
        await message.reply(
            "❌ Тест не выполнен.\n\n"
            f"Сообщений в истории: {status['history_count']}.\n"
            "Также проверь, что в memes.db есть существующие локальные картинки."
        )

# --- Сбор медиа ---

@router.message(F.photo)
async def collect_photo(message: Message):
    file_id = message.photo[-1].file_id
    await add_photo(message.chat.id, file_id)
    if message.caption:
        if not re.search(r"(?i)^[Ss]\s+[GgCcHhRrIi]", message.caption):
            if message.chat.type == "private" and DISABLE_AUTO_REPLY:
                return
            await handle_ai_interaction(message, message.caption)

@router.message(F.animation)
async def collect_gif(message: Message):
    await add_media(message.chat.id, message.animation.file_id, "gif")

@router.message(F.video)
async def collect_video(message: Message):
    await add_media(message.chat.id, message.video.file_id, "video")

# --- Авто-демотиватор (AI сам генерирует картинку) ---

async def _try_make_demot(message: Message, text: str) -> bool:
    """Если текст содержит [DEMOT], генерирует картинку+демотиватор вместо текста."""
    m = re.search(r'\[DEMOT\]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\[/DEMOT\]', text, re.DOTALL)
    if not m:
        return False
    img_desc = m.group(1).strip()
    title = m.group(2).strip().upper()
    subtitle = m.group(3).strip()

    # Кулдаун — не чаще раза в 2 часа на чат
    now = time.time()
    last = _last_demot_time.get(message.chat.id, 0)
    if now - last < _DEMOT_COOLDOWN_SECONDS:
        logger.info("Demot cooldown active for chat %s, dropping DEMOT text", message.chat.id)
        return True  # тег есть, но кулдаун — просто молча пропускаем

    try:
        await message.bot.send_chat_action(message.chat.id, "upload_photo", business_connection_id=message.business_connection_id)
        img_bytes = await generate_image(img_desc)
        loop = asyncio.get_event_loop()
        demot_bytes = await loop.run_in_executor(None, lambda: make_demotivator(img_bytes, title, subtitle))
        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=BufferedInputFile(demot_bytes, filename="demotivator.png"),
            caption=f"🤖 <b>{title}</b>\n<i>{subtitle}</i>",
            parse_mode="HTML",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id,
        )
        _last_demot_time[message.chat.id] = time.time()
        logger.info("Auto-demotivator sent to chat %s: %s | %s", message.chat.id, title, subtitle)
        return True
    except Exception as e:
        logger.error("Auto-demotivator failed: %s", e)
        try:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=f"❌ Не удалось сделать демотиватор: {e}",
                reply_to_message_id=message.message_id,
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
        return True


async def _handle_search_flow(reply: str, context: str, chat_id: int, image_url: str = None, user_name: str = "") -> str:
    """Если ответ содержит [SEARCH], выполняет web_search и переспрашивает AI."""
    m = re.search(r'\[SEARCH\]\s*(.+?)\s*\[/SEARCH\]', reply, re.DOTALL)
    if not m:
        return reply

    query = m.group(1).strip()
    logger.info("AI requested web search: %s", query)

    try:
        result = await web_search(query, max_results=5)
        if result:
            search_info = "\n".join(f"{r['title']}: {r['body']}" for r in result)
            prompt = (
                f"{context}\n\n"
                f"Результаты поиска по запросу «{query}»:\n{search_info}\n\n"
                f"Ответь на исходное сообщение с учётом этой информации."
            )
            final = await _ask(prompt, image_url=image_url, user_name=user_name)
            if final and not final.startswith("❌"):
                return final
    except Exception as e:
        logger.error(f"Search flow error: {e}")

    return re.sub(r'\[SEARCH\].*?\[/SEARCH\]', '', reply, flags=re.DOTALL).strip()


# --- Глобальные обработчики ---
async def handle_ai_interaction(message: Message, content: str, bot_mention: str = "", intent_context: str = None):
    """Общая логика ответа через ИИ."""
    clean_text = content
    if bot_mention:
        clean_text = re.sub(rf"(?i){bot_mention}\s*", "", content).strip()
    
    if not clean_text: clean_text = "Привет!"

    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    clean_text = f"Сегодня {now_str}. {clean_text}"

    biz_id = message.business_connection_id

    # Контекст "продолжай" — если отвечают на сообщение бота
    reply_ctx = None
    if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot:
        prev = last_bot_reply.get(message.chat.id) or message.reply_to_message.text
        ctx = last_bot_ctx.get(message.chat.id, {})
        user_msg = ctx.get("user_msg", "")
        if prev:
            reply_ctx = prev
            if user_msg and re.search(r"(?iu)^\s*(?:продолж(?:ай|и|ить)|давай\s+дальше|ещё|дальше)\b", clean_text):
                clean_text = (
                    f"Пользователь спросил: \"{user_msg}\"\n\n"
                    f"Ты начал отвечать: \"{prev}\"\n\n"
                    f"Пользователь просит продолжить: \"{clean_text}\"\n\n"
                    f"Продолжи свою мысль с того места, где остановился."
                )
            elif prev:
                clean_text = (
                    f"Ты ранее написал: \"{prev}\"\n\n"
                    f"Пользователь отвечает: \"{clean_text}\"\n\n"
                    f"Продолжи свою мысль."
                )

    # Режим "классический" — просто цитата из истории
    mode = await get_intelligence(message.chat.id)
    if mode == "classic":
        phrase = get_random_message(message.chat.id)
        if phrase:
            try:
                await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=phrase,
                    reply_to_message_id=message.message_id,
                    business_connection_id=biz_id
                )
            except Exception as e:
                logger.error(f"Classic reply error: {e}")
            return

    try:
        await message.bot.send_chat_action(message.chat.id, "typing", business_connection_id=biz_id)
        
        image_url = None
        photo = message.photo[-1] if message.photo else (message.reply_to_message.photo[-1] if message.reply_to_message and message.reply_to_message.photo else None)
        
        if photo:
            try:
                file = await message.bot.get_file(photo.file_id)
                os.makedirs("data/temp", exist_ok=True)
                tmp_path = f"data/temp/{photo.file_id}.jpg"
                await message.bot.download_file(file.file_path, tmp_path)
                with open(tmp_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                    image_url = f"data:image/jpeg;base64,{img_b64}"
                if os.path.exists(tmp_path): os.remove(tmp_path)
            except Exception as vision_err:
                logger.error(f"Vision failed: {vision_err}")

        if intent_context and not reply_ctx:
            clean_text = f"{clean_text}\n\nКонтекст: {intent_context}"

        # Добавляем историю чата для контекста (ЛС)
        if not reply_ctx:
            chat_history = format_history(message.chat.id, limit=2)
            if chat_history:
                clean_text = (
                    f"Вот история вашего диалога:\n{chat_history}\n\n"
                    f"Новое сообщение: \"{clean_text}\"\n\n"
                    f"Ответь на него, учитывая контекст выше."
                )

        custom_style = style_instruction(message.chat.id)
        user_name = message.from_user.full_name if message.from_user else ""
        if not intent_context:
            clean_text += (
                " ВАЖНО: Ты НЕ ЗНАЕШЬ актуальные адреса, телефоны, цены, рейтинги, названия заведений и режим работы."
                " Если вопрос про конкретные места, магазины, услуги, адреса или контакты — НЕ ВЫДУМЫВАЙ."
                " Напиши только [SEARCH] запрос [/SEARCH] и больше ничего. Дождись результатов поиска."
            )
        reply = await _ask(clean_text, max_tokens=1200, image_url=image_url, sys_prompt=custom_style if custom_style else None, user_name=user_name)
        if reply and not reply.startswith("❌"):
            reply = await _handle_search_flow(reply, clean_text, message.chat.id, image_url, user_name)
            if await _try_make_demot(message, reply):
                last_bot_reply[message.chat.id] = reply
                last_bot_ctx[message.chat.id] = {"reply": reply, "user_msg": content, "intent": intent_context}
            else:
                await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=reply,
                    reply_to_message_id=message.message_id,
                    business_connection_id=biz_id
                )
                last_bot_reply[message.chat.id] = reply
                last_bot_ctx[message.chat.id] = {"reply": reply, "user_msg": content, "intent": intent_context}
            await add_message(message.chat.id, "Chatrix", reply)
        else:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=f"⚠️ ИИ недоступен: {reply}",
                reply_to_message_id=message.message_id,
                business_connection_id=biz_id
            )
    except Exception as e:
        logger.error(f"AI Error: {e}")

@router.message()
async def final_handler(message: Message):
    if message.from_user and message.from_user.is_bot:
        return
    content = message.text or message.caption or ""
    if not content: return

    # Команды
    if re.search(r"(?i)^(@\w+\s*)?[Ss]\s+[GgCcHhRrIiTt]", content) or content.startswith("/"):
        return

    me = await message.bot.get_me()
    bot_mention = f"@{me.username}".lower()
    
    is_private = (message.chat.type == "private")
    is_mentioned = bot_mention in content.lower()

    # История
    username = message.from_user.username or message.from_user.first_name or "?"
    reply_to_username = ""
    if message.reply_to_message and message.reply_to_message.from_user:
        reply_to_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name or ""
    history_count = await add_message(message.chat.id, username, content, reply_to_username=reply_to_username)

    user_id = message.from_user.id if message.from_user else 0

    # AI Reaction (12% chance)
    if random.random() < 0.12:
        asyncio.create_task(send_ai_reaction(message, content, chance=1.0))

    # Анти-спам (пропускаем админов и команды)
    is_admin = user_id in ADMIN_IDS if user_id else False
    if is_ratelimited(message.chat.id, user_id, is_admin=is_admin, is_command=False):
        return

    # Упоминание (отключено по ТЗ)
    if is_mentioned:
        logger.info("Упоминание пропущено по ТЗ (заменено на инлайн-мемы).")
        return

    # Intent Detection — погода/время из контекста
    intent_tool = determine_tool(content)
    intent_context = None
    if intent_tool == "weather":
        weather = await get_weather()
        if weather:
            intent_context = f"Актуальная погода в Павлодаре: {weather}"
    elif intent_tool == "time":
        intent_context = f"Текущее время: {datetime.now().strftime('%H:%M')}"
    elif intent_tool == "web_search":
        result = await web_search(content, max_results=5)
        if result:
            intent_context = "\n".join(f"{r['title']}: {r['body']}" for r in result)

    # Стикер (шанс из настроек чата + случайный из паков)
    sticker_packs_path = "data/sticker_packs.json"
    if os.path.exists(sticker_packs_path):
        try:
            with open(sticker_packs_path, "r", encoding="utf-8") as f:
                packs_data = json.load(f)
            pack_names = packs_data.get("sticker_sets", [])
            style_settings_path = "data/crazybot_chat_settings.json"
            sticker_chance = 0.05
            if os.path.exists(style_settings_path):
                try:
                    with open(style_settings_path, "r", encoding="utf-8") as f:
                        style_data = json.load(f)
                    chat_style = style_data.get(str(message.chat.id), {})
                    if isinstance(chat_style, dict):
                        sticker_chance = float(chat_style.get("sticker_chance", sticker_chance))
                except Exception:
                    pass
            if pack_names and random.random() < sticker_chance:
                pack = random.choice(pack_names)
                try:
                    sticker_set = await message.bot.get_sticker_set(pack)
                    if sticker_set and sticker_set.stickers:
                        sticker = random.choice(sticker_set.stickers)
                        await message.bot.send_sticker(
                            chat_id=message.chat.id,
                            sticker=sticker.file_id,
                            reply_to_message_id=message.message_id,
                            business_connection_id=message.business_connection_id
                        )
                except Exception:
                    pass
        except Exception:
            pass

    # Auto-Vision (8% шанс на фото)
    if message.photo and random.random() < 0.08:
        asyncio.create_task(_auto_vision_comment(message, content))

    # Один общий редкий механизм для автоконтента: мем или демотиватор.
    if not is_private and await maybe_send_auto_content(
        message,
        history_count=history_count,
    ):
        return

    # Автоответы в ЛС и группах
    if is_private:
        if DISABLE_AUTO_REPLY: return
        history = get_history(message.chat.id)
        now = time.time()
        reply_every = max(1, int(get_chat_settings(message.chat.id).get("reply_every", 10)))
        should_reply = (len(history) % reply_every == 0)
        if not should_reply:
            last_time = last_bot_msg_time.get(message.chat.id, 0)
            should_reply = (now - last_time > 60)
        if not should_reply and message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot:
            should_reply = True
        if should_reply:
            await handle_ai_interaction(message, content, bot_mention, intent_context=intent_context)
            last_bot_msg_time[message.chat.id] = now
    else:
        reply_every = max(1, int(get_chat_settings(message.chat.id).get("reply_every", 10)))
        chance = max(1, 100 // reply_every)
        if message.chat.type != "supergroup":
            chance /= 5
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot
        if is_reply_to_bot or random.randint(1, 100) <= chance:
            history = format_history(message.chat.id, limit=2)
            reply_ctx = ""
            if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot:
                prev = last_bot_reply.get(message.chat.id) or message.reply_to_message.text or ""
                ctx = last_bot_ctx.get(message.chat.id, {})
                user_msg = ctx.get("user_msg", "")
                if user_msg and re.search(r"(?iu)^\s*(?:продолж(?:ай|и|ить)|давай\s+дальше|ещё|дальше)\b", content):
                    reply_ctx = f"Пользователь спросил: \"{user_msg}\". Ты начал отвечать: \"{prev}\""
                else:
                    reply_ctx = prev
            reply = await gen_smart_reply(history, content, chat_id=message.chat.id, web=intent_context, user_name=message.from_user.full_name if message.from_user else "", reply_context=reply_ctx)
            if reply and not reply.startswith("❌"):
                context_for_search = f"История чата:\n{history}\n\nНовое сообщение: {content}"
                reply = await _handle_search_flow(reply, context_for_search, message.chat.id, user_name=message.from_user.full_name if message.from_user else "")
                if not await _try_make_demot(message, reply):
                    await message.bot.send_message(
                        chat_id=message.chat.id,
                        text=reply,
                        reply_to_message_id=message.message_id,
                        business_connection_id=message.business_connection_id
                    )
                last_bot_reply[message.chat.id] = reply
                last_bot_ctx[message.chat.id] = {"reply": reply, "user_msg": content}
                await add_message(message.chat.id, "Chatrix", reply)


@router.message(F.text.regexp(r"^[01\s]{16,}$"))
async def decode_binary(message: Message):
    bits = message.text.replace(" ", "").replace("\t", "").replace("\n", "")
    if len(bits) % 8 != 0:
        bits = bits[:-(len(bits) % 8)]
    text = "".join(chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8))
    if text.strip():
        await message.bot.send_message(
            message.chat.id,
            f"🔓 {text}",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id,
        )


@router.message(F.text.regexp(r"^[0-9a-fA-F\s]{8,}$"))
async def decode_hex(message: Message):
    hex_str = message.text.replace(" ", "").replace("\t", "").replace("\n", "")
    if not re.search(r"[a-fA-F]", hex_str):
        return
    if len(hex_str) % 2 != 0:
        hex_str = hex_str[:-1]
    text = bytes.fromhex(hex_str).decode("utf-8", errors="ignore")
    if text.strip():
        await message.bot.send_message(
            message.chat.id,
            f"🔓 {text}",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id,
        )


async def _auto_vision_comment(message: Message, caption: str):
    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        os.makedirs("data/temp", exist_ok=True)
        tmp_path = f"data/temp/auto_vision_{photo.file_id}.jpg"
        await message.bot.download_file(file.file_path, tmp_path)
        with open(tmp_path, "rb") as f:
            import base64
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            image_url = f"data:image/jpeg;base64,{img_b64}"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        reply = await _ask(f"Коротко (до 30 слов) опиши что на этом фото. {caption}", image_url=image_url)
        if reply and not reply.startswith("❌"):
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=reply,
                reply_to_message_id=message.message_id,
                business_connection_id=message.business_connection_id
            )
    except Exception as e:
        logger.error(f"[AUTO-VISION] {e}")
