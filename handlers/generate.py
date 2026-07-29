"""
Хэндлеры генерации контента: S g, S g w, S g p, S g d, S g d ai, S g m, S g a
"""

import asyncio
import inspect
import functools
import random
import re
import base64
import os

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)

from utils.access import can_use_commands, is_admin
from utils.cooldown import check_cooldown, set_cooldown
from utils.history import format_history
from utils import ai
from utils.likes import vote as likes_vote, register_demot, top_examples
from utils.native_features import generate_image
from utils.demotivator import make_demotivator

import logging

logger = logging.getLogger(__name__)

router = Router()


async def _check(message: Message) -> bool:
    logger.info(f"Checking access for user {message.from_user.id} in chat {message.chat.id}")
    if not await can_use_commands(message):
        logger.warning(f"Access denied for user {message.from_user.id}")
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="⛔ У вас нет доступа к командам.",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
        return False
    logger.info("Access granted")
    return True


async def _run_ai(func, *args, **kwargs):
    """
    Run func which can be sync or async. If func returns an awaitable, await it.
    Otherwise run it in the default executor.
    """
    loop = asyncio.get_event_loop()
    logger.info(f"Running AI task: {getattr(func, '__name__', str(func))}")
    try:
        res = func(*args, **kwargs)
        if inspect.isawaitable(res):
            result = await res
        else:
            # wrap call with functools.partial to preserve args/kwargs
            result = await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
        logger.info(f"AI task completed")
        return result
    except Exception as e:
        logger.error(f"Error in AI task: {e}")
        return f"❌ Ошибка: {e}"


def _get_history(chat_id: int) -> str:
    return format_history(chat_id, limit=2, shuffle_past=True)


def _ai_likes_kb(message_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """Кнопки лайков — только для S g d ai."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="👍 0",
            callback_data=f"demot_vote:up:{message_id}:{chat_id}",
        ),
        InlineKeyboardButton(
            text="👎 0",
            callback_data=f"demot_vote:down:{message_id}:{chat_id}",
        ),
    ]])


# ─── S g — панель генерации ───────────────────────────────────────────────────

def _gen_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Текст", callback_data="gen_text"),
            InlineKeyboardButton(text="🔤 Слово", callback_data="gen_word"),
        ],
        [
            InlineKeyboardButton(text="📊 Опрос", callback_data="gen_poll"),
            InlineKeyboardButton(text="😂 Мем", callback_data="gen_meme"),
        ],
        [
            InlineKeyboardButton(text="🖼 Демотиватор", callback_data="gen_demot"),
            InlineKeyboardButton(text="🎨 Стикер", callback_data="gen_sticker"),
        ],
        [
            InlineKeyboardButton(text="🤖 Демот AI", callback_data="gen_demot_ai"),
            InlineKeyboardButton(text="🤣 Анекдот", callback_data="gen_joke"),
        ],
        [
            InlineKeyboardButton(text="📖 Длинный текст", callback_data="gen_long"),
        ],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="gen_close")],
    ])


@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s*$"))
async def cmd_gen_panel(message: Message):
    if not await _check(message):
        return
    await message.bot.send_message(
        chat_id=message.chat.id,
        text="🎲 <b>Генерация контента</b>\n\nВыберите что сгенерировать:",
        reply_markup=_gen_panel_kb(),
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )


@router.callback_query(F.data == "gen_close")
async def cb_gen_close(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.delete_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            business_connection_id=biz_id
        )
    except Exception:
        pass
    await call.answer()


# ─── S g q — викторина ───────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Qq]\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Qq]\s*$"))
async def cmd_gen_quiz(message: Message):
    if not await _check(message):
        return
    from utils.quiz import generate_quiz_questions
    questions = generate_quiz_questions(message.chat.id, limit=1)
    if not questions:
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="❌ Недостаточно истории чата!",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
        return
    
    q = questions[0]
    await message.bot.send_poll(
        chat_id=message.chat.id,
        question=q["question"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        is_anonymous=False,
        business_connection_id=message.business_connection_id
    )


# ─── S g p — опрос ───────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Pp]\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Pp]\s*$"))
async def cmd_gen_poll(message: Message):
    if not await _check(message):
        return
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="📊 Генерирую опрос...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )
    data = None
    try:
        data = await ai.gen_poll_data(history, chat_id=message.chat.id)
    except Exception as e:
        logger.exception(f"ai.gen_poll_data failed: {e}")

    # Validate data and fallback to a safe poll generator
    def _is_valid_poll(d):
        return (
            isinstance(d, dict)
            and isinstance(d.get("question"), str)
            and isinstance(d.get("options"), list)
            and 2 <= len(d.get("options")) <= 10
            and all(isinstance(o, str) and o.strip() for o in d.get("options"))
        )

    # If question contains only emojis/symbols (no letters/digits), treat as invalid
    import re
    def _has_text_chars(s: str) -> bool:
        return bool(re.search(r"[0-9A-Za-zА-Яа-яЁё]", s))


    if not _is_valid_poll(data):
        from utils.history import get_poll_data
        data = get_poll_data(message.chat.id)

    # reject questions that are emoji-only (no text characters)
    if data and isinstance(data.get("question"), str) and not _has_text_chars(data["question"]):
        logger.info("Generated poll question contains no text characters, falling back to history-based poll")
        from utils.history import get_poll_data
        data = get_poll_data(message.chat.id)

    if not _is_valid_poll(data):
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="❌ Не удалось сгенерировать опрос — в истории недостаточно сообщений.",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
        return

    try:
        await message.bot.send_poll(
            chat_id=message.chat.id,
            question=data["question"],
            options=data["options"],
            is_anonymous=False,
            business_connection_id=message.business_connection_id
        )
    except Exception as e:
        logger.exception(f"answer_poll failed: {e}")
        await message.bot.send_message(
            chat_id=message.chat.id,
            text=f"❌ Не удалось создать опрос: {e}",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )


# ─── S g <число> ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+(\d+)\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+(\d+)\s*$"))
async def cmd_gen_text_len(message: Message):
    if not await _check(message):
        return
    text = re.sub(r"(?i)^@\w+\s*", "", message.text).lstrip()
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+(\d+)", text)
    length = max(1, min(250, int(m.group(1))))
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="✍️ Генерирую текст...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

    history = _get_history(message.chat.id)
    text_res = await ai.gen_text("", length, history)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=wait.message_id,
        text=text_res,
        business_connection_id=message.business_connection_id
    )


# ─── S g <начало> ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+(?![wWdDmMaApPlLrRqQsS])(.+)\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+(?![wWdDmMaApPlLrRqQsS])(.+)\s*$"))
async def cmd_gen_text_start(message: Message):
    if not await _check(message):
        return
    text = re.sub(r"(?i)^@\w+\s*", "", message.text).lstrip()
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+(.+)", text)
    start = m.group(1).strip()
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="✍️ Генерирую текст...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

    history = _get_history(message.chat.id)
    text_res = await ai.gen_text(start, 0, history)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=wait.message_id,
        text=text_res,
        business_connection_id=message.business_connection_id
    )


# ─── S g m — мем ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Mm]\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Mm]\s*$"))
async def cmd_gen_meme(message: Message):
    if not await _check(message):
        return
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="😂 Генерирую мем...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )
    history = _get_history(message.chat.id)
    if not history:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=wait.message_id,
            text="❌ В этом чате еще слишком мало сообщений для мема!",
            business_connection_id=message.business_connection_id
        )
        return
    title, subtitle = await ai.gen_meme_caption(history=history)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=wait.message_id,
        text=f"😂 <b>{title.upper()}</b>\n<i>{subtitle}</i>",
        parse_mode="HTML",
        business_connection_id=message.business_connection_id
    )


# ─── Общий хелпер для получения фото ─────────────────────────────────────────

def _get_media_file_id(message: Message) -> tuple[str | None, str]:
    """Возвращает file_id и тип медиа."""
    if message.reply_to_message:
        rm = message.reply_to_message
        if rm.photo:
            return rm.photo[-1].file_id, "photo"
        if rm.animation:
            return rm.animation.file_id, "animation"
        if rm.video:
            return rm.video.file_id, "video"
        if rm.video_note:
            return rm.video_note.file_id, "video_note"
            
    if message.photo:
        return message.photo[-1].file_id, "photo"
    if message.animation:
        return message.animation.file_id, "animation"
    if message.video:
        return message.video.file_id, "video"
    if message.video_note:
        return message.video_note.file_id, "video_note"
        
    from utils.history import get_random_photo, get_random_media
    import random
    
    # Случайный выбор типа медиа для разнообразия (50/50)
    if random.choice([True, False]):
        gif = get_random_media(message.chat.id, "gif")
        if gif: return gif, "animation"
        photo = get_random_photo(message.chat.id)
        return photo, "photo" if photo else ("None", "none")
    else:
        photo = get_random_photo(message.chat.id)
        if photo: return photo, "photo"
        gif = get_random_media(message.chat.id, "gif")
        return gif, "animation" if gif else ("None", "none")


async def _shorten(text: str, max_words: int) -> str:
    """Укорачивает текст до нужного количества слов."""
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


async def _download_media(message: Message, file_id: str, suffix=".jpg") -> str:
    """Загружает медиа и возвращает путь к файлу."""
    import os
    file = await message.bot.get_file(file_id)
    # Создаем временную директорию если нет
    os.makedirs("data/temp", exist_ok=True)
    path = f"data/temp/{file_id}{suffix}"
    await message.bot.download_file(file.file_path, path)
    return path


async def _render_video_demot(video_path: str, title: str, subtitle: str) -> str:
    loop = asyncio.get_event_loop()
    from utils.demotivator import make_video_demotivator
    return await loop.run_in_executor(None, lambda: make_video_demotivator(video_path, title, subtitle))


async def _render_demot(photo_data: bytes, title: str, subtitle: str, is_gif: bool = False) -> bytes:
    loop = asyncio.get_event_loop()
    from utils.demotivator import make_demotivator, make_gif_demotivator
    func = make_gif_demotivator if is_gif else make_demotivator
    return await loop.run_in_executor(None, lambda: func(photo_data, title, subtitle))

async def _render_sticker(photo_data: bytes) -> bytes:
    loop = asyncio.get_event_loop()
    from utils.demotivator import make_sticker
    return await loop.run_in_executor(None, lambda: make_sticker(photo_data))


async def _send_demotivator_ai(message: Message, photo_data: bytes, title: str, subtitle: str) -> None:
    """S g d ai — с кнопками лайков и сохранением для обучения."""
    img_bytes = await _render_demot(photo_data, title, subtitle, is_gif=False)
    sent = await message.reply_photo(BufferedInputFile(img_bytes, filename="demot.png"))
    register_demot(sent.message_id, sent.chat.id, title, subtitle)
    kb = _ai_likes_kb(sent.message_id, sent.chat.id)
    await sent.edit_reply_markup(reply_markup=kb)


async def _send_demotivator(message: Message, photo_data: bytes, title: str, subtitle: str) -> Message:
    """S g d — без лайков."""
    img_bytes = await _render_demot(photo_data, title, subtitle, is_gif=False)
    return await message.reply_photo(BufferedInputFile(img_bytes, filename="demot.png"))


# ─── S g s — стикер (обрезка в 1:1) ───────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Ss]\s*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Ss]\s*$"))
async def cmd_gen_sticker(message: Message):
    if not await _check(message):
        return

    file_id, media_type = _get_media_file_id(message)
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="🎨 Создаю стикер...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

    if file_id and file_id != "None":
        photo_data = await _download_media(message, file_id)
        img_bytes = await _render_sticker(photo_data)
        try:
            await wait.delete()
        except Exception: pass
        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=BufferedInputFile(img_bytes, filename="sticker.png"),
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
    else:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=wait.message_id,
            text="🎨 <i>Для создания стикера нужно реплаем на фото или просто отправить фото с командой!</i>",
            parse_mode="HTML",
            business_connection_id=message.business_connection_id
        )


# ─── S g d — демотиватор (оригинал) ──────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Dd][\s,.]*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Dd][\s,.]*$"))
async def cmd_gen_demot(message: Message):
    if not await _check(message):
        return

    file_id, media_type = _get_media_file_id(message)
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="🖼 Генерирую демотиватор...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

    biz_id = message.business_connection_id

    from utils.history import get_two_random_messages
    history = _get_history(message.chat.id)
    if not history:
        # Если истории нет, используем заглушку или случайные слова
        title, subtitle = "ПУСТОТА", "в чате еще нет сообщений"
    else:
        title, subtitle = get_two_random_messages(message.chat.id)
        
    # Используем ai._shorten если он есть, иначе просто обрезаем
    try:
        title = await _shorten(title, max_words=5)
        subtitle = await _shorten(subtitle, max_words=7)
    except Exception as e:
        logger.warning(f"Shorten failed: {e}")

    if file_id and file_id != "None":
        try:
            import os
            from aiogram.types import FSInputFile
            
            # Определяем расширение для загрузки
            suffix = ".mp4" if media_type in ["video", "video_note", "animation"] else ".jpg"
            file_path = await _download_media(message, file_id, suffix=suffix)
            if media_type in ["video", "video_note", "animation"]:
                # Рендерим видео-демотиватор
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=wait.message_id,
                        text="🎬 Обрабатываю анимацию/видео...",
                        business_connection_id=biz_id
                    )
                except Exception: pass
                
                out_path = await _render_video_demot(file_path, title, subtitle)
                
                try:
                    await wait.delete()
                except Exception: pass
                
                # Отправляем как анимацию
                # Используем BufferedInputFile чтобы задать имя .gif (помогает Telegram распознать анимацию)
                with open(out_path, "rb") as f:
                    gif_data = f.read()
                
                await message.bot.send_animation(
                    chat_id=message.chat.id,
                    animation=BufferedInputFile(gif_data, filename="animation.gif"),
                    width=600, height=600,
                    reply_to_message_id=message.message_id,
                    business_connection_id=biz_id
                )
                
                # Чистим временные файлы
                if os.path.exists(file_path): os.remove(file_path)
                if os.path.exists(out_path): os.remove(out_path)

            else:
                # Обычный фото-демотиватор
                with open(file_path, "rb") as f:
                    photo_data = f.read()
                
                is_gif = (media_type == "animation")
                img_bytes = await _render_demot(photo_data, title, subtitle, is_gif=is_gif)
                
                try:
                    await wait.delete()
                except Exception: pass
                
                if is_gif:
                    await message.bot.send_animation(
                        chat_id=message.chat.id,
                        animation=BufferedInputFile(img_bytes, filename="demot.gif"),
                        width=600, height=600,
                        reply_to_message_id=message.message_id,
                        business_connection_id=biz_id
                    )
                else:
                    await message.bot.send_photo(
                        chat_id=message.chat.id,
                        photo=BufferedInputFile(img_bytes, filename="demot.png"),
                        reply_to_message_id=message.message_id,
                        business_connection_id=biz_id
                    )
                
                if os.path.exists(file_path): os.remove(file_path)
                
        except Exception as e:
            logger.exception("Demotivator generation failed")
            err_msg = str(e)
            if "identify" in err_msg:
                err_msg = "Не удалось распознать формат файла. Попробуйте другое фото или гифку."
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=wait.message_id,
                    text=f"❌ Ошибка генерации: {err_msg}\nТип медиа: {media_type}",
                    business_connection_id=biz_id
                )
            except Exception:
                await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"❌ Ошибка генерации: {err_msg}",
                    business_connection_id=biz_id
                )
    else:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wait.message_id,
                text=f"🖼 <b>{title}</b>\n<i>{subtitle}</i>\n\n<i>💡 Медиа в чате пока нет — пришли фотку или гифку!</i>",
                parse_mode="HTML",
                business_connection_id=biz_id
            )
        except Exception: pass


# ─── S g d ai — демотиватор с AI-анализом ────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Dd]\s+[Aa][Ii][\s,.]*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Dd]\s+[Aa][Ii][\s,.]*$"))
async def cmd_gen_demot_ai(message: Message):
    if not await _check(message):
        return

    file_id, media_type = _get_media_file_id(message)
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="🤖 Анализирую чат и генерирую демотиватор...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

    biz_id = message.business_connection_id
    history = _get_history(message.chat.id)

    # Few-shot: топ лайкнутых демотиваторов этого чата
    examples = top_examples(message.chat.id, limit=5)
    examples_block = ""
    if examples:
        lines = "\n".join(
            f'  ЗАГОЛОВОК: {e["title"]}\n  ПОДПИСЬ: {e["subtitle"]}  (рейтинг: +{e["score"]})'
            for e in examples
        )
        examples_block = (
            f"\nПримеры демотиваторов, которые понравились этому чату (учитывай их стиль):\n"
            f"{lines}\n"
        )

    try:
        file_path = None
        image_url = None
        
        # Предварительная загрузка фото для Vision анализа
        if file_id and file_id != "None" and media_type == "photo":
            try:
                file_path = await _download_media(message, file_id, suffix=".jpg")
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode("utf-8")
                        image_url = f"data:image/jpeg;base64,{img_b64}"
            except Exception as vision_err:
                logger.error(f"Vision preparation failed: {vision_err}")

        prompt = (
            f"Ты генератор демотиваторов. Проанализируй контекст (историю чата "
            f"{'и прикрепленное изображение ' if image_url else ''}) и придумай "
            f"язвительный/смешной демотиватор по ситуации.\n\n"
            f"Сообщения чата:\n{history}\n"
            f"{examples_block}\n"
            f"Ответь строго в формате двух строк:\n"
            f"ЗАГОЛОВОК: <не более 5 слов, капслок не нужен>\n"
            f"ПОДПИСЬ: <не более 7 слов>\n\n"
            f"Только эти две строки, никакого другого текста."
        )

        raw = await ai._ask(prompt, image_url=image_url)

        title = "СИТУАЦИЯ"
        subtitle = "комментарии излишни"
        if raw:
            lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
            for line in lines:
                if line.upper().startswith("ЗАГОЛОВОК:"):
                    title = line.split(":", 1)[1].strip()
                elif line.upper().startswith("ПОДПИСЬ:"):
                    subtitle = line.split(":", 1)[1].strip()

        title    = await _shorten(title, max_words=5)
        subtitle = await _shorten(subtitle, max_words=7)

        if file_id and file_id != "None":
            from aiogram.types import FSInputFile
            
            # Если мы уже скачали файл для Vision, используем его
            if not file_path:
                suffix = ".mp4" if media_type in ["video", "video_note", "animation"] else ".jpg"
                file_path = await _download_media(message, file_id, suffix=suffix)
            
            if media_type in ["video", "video_note", "animation"]:
                # Рендерим видео-демотиватор
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=wait.message_id,
                        text="🎬 Обрабатываю анимацию/видео...",
                        business_connection_id=biz_id
                    )
                except Exception: pass
                
                out_path = await _render_video_demot(file_path, title, subtitle)
                try:
                    await wait.delete()
                except Exception: pass
                
                # Отправляем как анимацию
                with open(out_path, "rb") as f:
                    gif_data = f.read()

                sent = await message.bot.send_animation(
                    chat_id=message.chat.id,
                    animation=BufferedInputFile(gif_data, filename="animation.gif"),
                    width=600, height=600,
                    reply_to_message_id=message.message_id,
                    business_connection_id=biz_id
                )
                register_demot(sent.message_id, sent.chat.id, title, subtitle)
                kb = _ai_likes_kb(sent.message_id, sent.chat.id)
                try:
                    await message.bot.edit_message_reply_markup(
                        chat_id=sent.chat.id,
                        message_id=sent.message_id,
                        reply_markup=kb,
                        business_connection_id=biz_id
                    )
                except Exception: pass
                
                # Чистим временные файлы
                if os.path.exists(file_path): os.remove(file_path)
                if os.path.exists(out_path): os.remove(out_path)
            else:
                # Обычный фото-демотиватор
                with open(file_path, "rb") as f:
                    photo_data = f.read()
                
                is_gif = (media_type == "animation")
                img_bytes = await _render_demot(photo_data, title, subtitle, is_gif=is_gif)
                try:
                    await wait.delete()
                except Exception: pass
                
                if is_gif:
                    sent = await message.bot.send_animation(
                        chat_id=message.chat.id,
                        animation=BufferedInputFile(img_bytes, filename="demot.gif"),
                        width=600, height=600,
                        reply_to_message_id=message.message_id,
                        business_connection_id=biz_id
                    )
                else:
                    sent = await message.bot.send_photo(
                        chat_id=message.chat.id,
                        photo=BufferedInputFile(img_bytes, filename="demot.png"),
                        reply_to_message_id=message.message_id,
                        business_connection_id=biz_id
                    )
                    
                register_demot(sent.message_id, sent.chat.id, title, subtitle)
                kb = _ai_likes_kb(sent.message_id, sent.chat.id)
                try:
                    await message.bot.edit_message_reply_markup(
                        chat_id=sent.chat.id,
                        message_id=sent.message_id,
                        reply_markup=kb,
                        business_connection_id=biz_id
                    )
                except Exception: pass
                
                if os.path.exists(file_path): os.remove(file_path)
        else:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=wait.message_id,
                    text=f"🤖 <b>{title.upper()}</b>\n<i>{subtitle}</i>\n\n<i>💡 Медиа в чате пока нет — пришли фотку или гифку!</i>",
                    parse_mode="HTML",
                    business_connection_id=biz_id
                )
            except Exception: pass
    except Exception as e:
        logger.exception("AI Demotivator generation failed")
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wait.message_id,
                text=f"❌ Ошибка ИИ или генерации: {e}",
                business_connection_id=biz_id
            )
        except Exception:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=f"❌ Ошибка: {e}",
                business_connection_id=biz_id
            )


# ─── S g d g — демотиватор из сгенерированной картинки ────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Dd]\s+[Gg]\s+(.+)"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Dd]\s+[Gg]\s+(.+)"))
async def cmd_gen_demot_gen(message: Message):
    if not await _check(message):
        return

    desc = message.text.split(maxsplit=3)
    img_desc = desc[3] if len(desc) >= 4 else ""

    if not img_desc:
        await message.reply("Формат: S g d g <описание картинки>", business_connection_id=message.business_connection_id)
        return

    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="🎨 Рисую картинку...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )

    try:
        img_bytes = await generate_image(img_desc)

        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=wait.message_id,
            text="🤖 Придумываю подпись...",
            business_connection_id=message.business_connection_id
        )

        prompt = (
            f"Придумай заголовок (до 5 слов) и подпись (до 7 слов) для демотиватора "
            f"на тему: «{img_desc}». Ответь строго в формате:\n"
            f"ЗАГОЛОВОК: <текст>\nПОДПИСЬ: <текст>"
        )
        raw = await ai._ask(prompt, max_tokens=150)

        title = "ОЧЕНЬ ВАЖНО"
        subtitle = "просто чтобы ты знал"
        if raw:
            for line in raw.strip().splitlines():
                line = line.strip()
                if line.upper().startswith("ЗАГОЛОВОК:"):
                    title = line.split(":", 1)[1].strip()
                elif line.upper().startswith("ПОДПИСЬ:"):
                    subtitle = line.split(":", 1)[1].strip()
        title = title.upper()

        loop = asyncio.get_event_loop()
        demot_bytes = await loop.run_in_executor(None, lambda: make_demotivator(img_bytes, title, subtitle))

        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=wait.message_id,
            text="📤 Отправляю...",
            business_connection_id=message.business_connection_id
        )

        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=BufferedInputFile(demot_bytes, filename="demotivator.png"),
            caption=f"🤖 <b>{title}</b>\n<i>{subtitle}</i>",
            parse_mode="HTML",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
        await wait.delete()
    except Exception as e:
        logger.exception("Demotivator generation failed")
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wait.message_id,
                text=f"❌ Ошибка: {e}",
                business_connection_id=message.business_connection_id
            )
        except Exception:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=f"❌ Ошибка: {e}",
                business_connection_id=message.business_connection_id
            )


# ─── Колбэк лайков для демотиваторов ─────────────────────────────────────────

@router.callback_query(F.data.startswith("demot_vote:"))
async def cb_demot_vote(call: CallbackQuery):
    # demot_vote:up/down:message_id:chat_id
    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer()
        return
    _, vote_type, message_id, chat_id = parts
    score = likes_vote(int(message_id), int(chat_id), call.from_user.id, vote_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"👍 {score['likes']}" + (" ✓" if score["my_vote"] == "up" else ""),
            callback_data=f"demot_vote:up:{message_id}:{chat_id}",
        ),
        InlineKeyboardButton(
            text=f"👎 {score['dislikes']}" + (" ✓" if score["my_vote"] == "down" else ""),
            callback_data=f"demot_vote:down:{message_id}:{chat_id}",
        ),
    ]])
    
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb,
            business_connection_id=biz_id
        )
    except Exception:
        pass
    await call.answer("✓" if score["my_vote"] else "Голос снят")


# ─── S g a — анекдот ─────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Aa]"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?[Ss]\s+[Gg]\s+[Aa]"))
async def cmd_gen_joke(message: Message):
    logger.info(f"CMD_GEN_JOKE triggered with text: {message.text}")
    if not await _check(message):
        return
    
    # Очищаем текст от упоминания бота, если оно есть
    text = re.sub(r"(?i)^@\w+\s+", "", message.text)
    logger.info(f"Cleaned text: {text}")
        
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+[Aa](?:\s+(.+))?\s*$", text)
    start = m.group(1).strip() if m and m.group(1) else ""
    
    logger.info(f"Generating joke with start: '{start}'")
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="🤣 Генерирую анекдот...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )
    history = _get_history(message.chat.id)
    joke = await ai.gen_joke(start, history)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=wait.message_id,
        text=f"🤣 {joke}",
        business_connection_id=message.business_connection_id
    )


# ─── Колбэки из панели ────────────────────────────────────────────────────────

@router.callback_query(F.data == "gen_text")
async def cb_gen_text(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✍️ Генерирую текст...",
            business_connection_id=biz_id
        )
    except Exception: pass
    
    history = _get_history(call.message.chat.id)
    text = await ai.gen_text("", 0, history)
    
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_word")
async def cb_gen_word(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    history = _get_history(call.message.chat.id)
    word = await ai.gen_word(0, history)
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🔤 <b>{word}</b>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=f"🔤 <b>{word}</b>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_poll")
async def cb_gen_poll(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    history = _get_history(call.message.chat.id)
    data = await ai.gen_poll_data(history, chat_id=call.message.chat.id)
    if not data:
        await call.answer("❌ Ошибка!", show_alert=True)
        return
    
    try:
        await call.message.bot.delete_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            business_connection_id=biz_id
        )
    except Exception: pass

    try:
        if data.get("is_quiz"):
            await call.message.bot.send_poll(
                chat_id=call.message.chat.id,
                question=data["question"],
                options=data["options"],
                type="quiz",
                correct_option_id=data.get("correct_option_id", 0),
                is_anonymous=False,
                business_connection_id=biz_id
            )
        else:
            await call.message.bot.send_poll(
                chat_id=call.message.chat.id,
                question=data["question"],
                options=data["options"],
                is_anonymous=False,
                business_connection_id=biz_id
            )
    except Exception as e:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=f"❌ Ошибка: {e}",
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_meme")
async def cb_gen_meme(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="😂 Генерирую мем...",
            business_connection_id=biz_id
        )
    except Exception: pass
    
    history = _get_history(call.message.chat.id)
    title, subtitle = await ai.gen_meme_caption(history=history)
    
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"😂 <b>{title.upper()}</b>\n<i>{subtitle}</i>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=f"😂 <b>{title.upper()}</b>\n<i>{subtitle}</i>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_demot")
async def cb_gen_demot(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🖼 Генерирую демотиватор...",
            business_connection_id=biz_id
        )
    except Exception: pass
    
    from utils.history import get_two_random_messages
    title, subtitle = get_two_random_messages(call.message.chat.id)
    title    = await _shorten(title, max_words=5)
    subtitle = await _shorten(subtitle, max_words=7)
    
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🖼 <b>{title}</b>\n<i>{subtitle}</i>\n\n<i>💡 Для картинки используй S g d с реплаем на фото</i>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=f"🖼 <b>{title}</b>\n<i>{subtitle}</i>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_demot_ai")
async def cb_gen_demot_ai(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🤖 Анализирую чат...",
            business_connection_id=biz_id
        )
    except Exception: pass
    
    history = _get_history(call.message.chat.id)
    raw = await ai._ask(
        f"Ты генератор демотиваторов. Проанализируй последние сообщения чата и придумай "
        f"язвительный/смешной демотиватор по ситуации.\n\n"
        f"Сообщения чата:\n{history}\n\n"
        f"Ответь строго в формате двух строк:\n"
        f"ЗАГОЛОВОК: <не более 5 слов>\n"
        f"ПОДПИСЬ: <не более 7 слов>\n\n"
        f"Только эти две строки."
    )
    title = "СИТУАЦИЯ"
    subtitle = "комментарии излишни"
    if raw:
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        for line in lines:
            if line.upper().startswith("ЗАГОЛОВОК:"):
                title = line.split(":", 1)[1].strip()
            elif line.upper().startswith("ПОДПИСЬ:"):
                subtitle = line.split(":", 1)[1].strip()
    
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🤖 <b>{title.upper()}</b>\n<i>{subtitle}</i>\n\n<i>💡 Для картинки используй S g d ai с реплаем на фото</i>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=f"🤖 <b>{title.upper()}</b>\n<i>{subtitle}</i>",
            parse_mode="HTML",
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_joke")
async def cb_gen_joke(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🤣 Генерирую анекдот...",
            business_connection_id=biz_id
        )
    except Exception: pass
    
    history = _get_history(call.message.chat.id)
    joke = await ai.gen_joke("", history)
    
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🤣 {joke}",
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=f"🤣 {joke}",
            business_connection_id=biz_id
        )
    await call.answer()


@router.callback_query(F.data == "gen_long")
async def cb_gen_long(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✍️ Генерирую длинный текст...",
            business_connection_id=biz_id
        )
    except Exception: pass
    
    history = _get_history(call.message.chat.id)
    text = await ai.gen_long_text(history)
    
    try:
        await call.message.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            business_connection_id=biz_id
        )
    except Exception:
        await call.message.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            business_connection_id=biz_id
        )
    await call.answer()


# ─── S g r — случайный реплай из истории чата ────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Rr][\s,.]*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Rr][\s,.]*$"))
async def cmd_gen_reply(message: Message):
    if not await _check(message):
        return
    history = _get_history(message.chat.id)
    reply = await ai.gen_reply(history)
    await message.bot.send_message(
        chat_id=message.chat.id,
        text=reply,
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )


# ─── S g w — слово из истории чата ────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Ww][\s,.]*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Ww][\s,.]*$"))
async def cmd_gen_word(message: Message):
    if not await _check(message):
        return
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="🔤 Генерирую слово...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )
    history = _get_history(message.chat.id)
    word = await ai.gen_word(0, history)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=wait.message_id,
        text=f"🔤 <b>{word}</b>",
        parse_mode="HTML",
        business_connection_id=message.business_connection_id
    )


# ─── S g l — длинный текст ────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Ll][\s,.]*$"))
@router.business_message(F.text.regexp(r"(?i)^\s*(?:@\w+\s*)?\s*[Ss]\s+[Gg]\s+[Ll][\s,.]*$"))
async def cmd_gen_long(message: Message):
    if not await _check(message):
        return
    wait = await message.bot.send_message(
        chat_id=message.chat.id,
        text="📖 Генерирую длинный текст...",
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id
    )
    history = _get_history(message.chat.id)
    text = await ai.gen_long_text(history)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=wait.message_id,
        text=text,
        business_connection_id=message.business_connection_id
    )


# ─── Колбэк стикера из панели ─────────────────────────────────────────────────

@router.callback_query(F.data == "gen_sticker")
async def cb_gen_sticker(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    biz_id = call.message.business_connection_id
    await call.answer("🎨 Отправь S g s с реплаем на фото", show_alert=True)
