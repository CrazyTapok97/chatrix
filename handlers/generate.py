"""
Хэндлеры генерации контента: S g, S g w, S g p, S g d, S g d ai, S g m, S g a
"""

import asyncio
import random
import re

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
from config import MEM_TEMPLATES

router = Router()


async def _check(message: Message) -> bool:
    if not await can_use_commands(message):
        await message.reply("⛔ У вас нет доступа к командам.")
        return False
    return True


async def _run_ai(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def _get_history(chat_id: int) -> str:
    return format_history(chat_id, limit=50)


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
            InlineKeyboardButton(text="🤖 Демот AI", callback_data="gen_demot_ai"),
        ],
        [
            InlineKeyboardButton(text="🤣 Анекдот", callback_data="gen_joke"),
            InlineKeyboardButton(text="📖 Длинный текст", callback_data="gen_long"),
        ],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="gen_close")],
    ])


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]$"))
async def cmd_gen_panel(message: Message):
    if not await _check(message):
        return
    await message.reply(
        "🎲 <b>Генерация контента</b>\n\nВыберите что сгенерировать:",
        reply_markup=_gen_panel_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "gen_close")
async def cb_gen_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()


# ─── S g <число> ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+(\d+)$"))
async def cmd_gen_text_len(message: Message):
    if not await _check(message):
        return
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+(\d+)$", message.text)
    length = max(1, min(250, int(m.group(1))))
    wait = await message.reply("✍️ Генерирую текст...")
    history = _get_history(message.chat.id)
    text = await _run_ai(ai.gen_text, "", length, history)
    await wait.edit_text(text)


# ─── S g <начало> ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+(?![wWdDmMaApPlLrR])(.+)$"))
async def cmd_gen_text_start(message: Message):
    if not await _check(message):
        return
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+(.+)$", message.text)
    start = m.group(1).strip()
    wait = await message.reply("✍️ Генерирую текст...")
    history = _get_history(message.chat.id)
    text = await _run_ai(ai.gen_text, start, 0, history)
    await wait.edit_text(text)


# ─── S g l — длинный текст ───────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Ll]$"))
async def cmd_gen_long(message: Message):
    if not await _check(message):
        return
    wait = await message.reply("✍️ Генерирую длинный текст...")
    history = _get_history(message.chat.id)
    text = await _run_ai(ai.gen_long_text, history)
    await wait.edit_text(text)


# ─── S g w — слово ────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Ww](\s+\d+)?$"))
async def cmd_gen_word(message: Message):
    if not await can_use_commands(message):
        await message.reply("⛔ У вас нет доступа к командам.")
        return
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+[Ww](\s+(\d+))?$", message.text)
    length = int(m.group(2)) if m.group(2) else 0
    if length:
        length = max(1, min(50, length))
    history = _get_history(message.chat.id)
    word = await _run_ai(ai.gen_word, length, history)
    await message.reply(f"🔤 <b>{word}</b>", parse_mode="HTML")


# ─── S g p — опрос ───────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Pp]$"))
async def cmd_gen_poll(message: Message):
    if not await _check(message):
        return
    from utils.history import get_poll_data
    data = get_poll_data(message.chat.id)
    if not data:
        await message.reply("❌ Недостаточно сообщений в чате!")
        return
    wait = await message.reply("📊 Генерирую опрос...")
    await wait.delete()
    try:
        if data.get("is_quiz"):
            await message.answer_poll(
                question=data["question"],
                options=data["options"],
                type="quiz",
                correct_option_id=data.get("correct_option_id", 0),
                is_anonymous=False,
            )
        else:
            await message.answer_poll(
                question=data["question"],
                options=data["options"],
                is_anonymous=False,
            )
    except Exception as e:
        await message.reply(f"❌ Не удалось создать опрос: {e}")


# ─── S g m — мем ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Mm]$"))
async def cmd_gen_meme(message: Message):
    if not await _check(message):
        return
    template = random.choice(MEM_TEMPLATES)
    wait = await message.reply("😂 Генерирую мем...")
    history = _get_history(message.chat.id)
    caption = await _run_ai(ai.gen_meme_caption, template, history)
    await wait.edit_text(f"😂 <b>{template}</b>\n\n{caption}", parse_mode="HTML")


# ─── Общий хелпер для получения фото ─────────────────────────────────────────

def _get_photo_file_id(message: Message) -> str | None:
    if message.reply_to_message and message.reply_to_message.photo:
        return message.reply_to_message.photo[-1].file_id
    if message.photo:
        return message.photo[-1].file_id
    from utils.history import get_random_photo
    return get_random_photo(message.chat.id)


async def _download_photo(message: Message, file_id: str) -> bytes:
    file = await message.bot.get_file(file_id)
    photo_bytes = await message.bot.download_file(file.file_path)
    return photo_bytes.read()


async def _shorten(text: str, max_words: int = 6) -> str:
    if len(text.split()) <= max_words:
        return text
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: ai._ask(
            f"Перефразируй это сообщение в {max_words} слов или меньше. "
            f"Сохрани суть. Только текст без кавычек и пояснений.\n\n{text}"
        ))
        return result.strip()[:80] if result else text
    except Exception:
        return text


async def _render_demot(photo_data: bytes, title: str, subtitle: str) -> bytes:
    loop = asyncio.get_event_loop()
    from utils.demotivator import make_demotivator
    return await loop.run_in_executor(None, lambda: make_demotivator(photo_data, title, subtitle))


async def _send_demotivator_ai(message: Message, photo_data: bytes, title: str, subtitle: str) -> None:
    """S g d ai — с кнопками лайков и сохранением для обучения."""
    img_bytes = await _render_demot(photo_data, title, subtitle)
    sent = await message.reply_photo(BufferedInputFile(img_bytes, filename="demot.png"))
    register_demot(sent.message_id, sent.chat.id, title, subtitle)
    kb = _ai_likes_kb(sent.message_id, sent.chat.id)
    await sent.edit_reply_markup(reply_markup=kb)


async def _send_demotivator(message: Message, photo_data: bytes, title: str, subtitle: str) -> Message:
    """S g d — без лайков."""
    img_bytes = await _render_demot(photo_data, title, subtitle)
    await message.reply_photo(BufferedInputFile(img_bytes, filename="demot.png"))


# ─── S g d — демотиватор (оригинал) ──────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Dd]$"))
async def cmd_gen_demot(message: Message):
    if not await _check(message):
        return

    photo_file_id = _get_photo_file_id(message)
    wait = await message.reply("🖼 Генерирую демотиватор...")

    from utils.history import get_two_random_messages
    title, subtitle = get_two_random_messages(message.chat.id)
    title    = await _shorten(title, max_words=5)
    subtitle = await _shorten(subtitle, max_words=7)

    if photo_file_id:
        photo_data = await _download_photo(message, photo_file_id)
        await wait.delete()
        await _send_demotivator(message, photo_data, title, subtitle)
    else:
        await wait.edit_text(
            f"🖼 <b>{title}</b>\n<i>{subtitle}</i>\n\n"
            f"<i>💡 Фото из чата пока нет — пришли любую фотку!</i>",
            parse_mode="HTML",
        )


# ─── S g d ai — демотиватор с AI-анализом ────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Dd]\s+[Aa][Ii]$"))
async def cmd_gen_demot_ai(message: Message):
    if not await _check(message):
        return

    photo_file_id = _get_photo_file_id(message)
    wait = await message.reply("🤖 Анализирую чат и генерирую демотиватор...")

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

    raw = await _run_ai(
        ai._ask,
        f"Ты генератор демотиваторов. Проанализируй последние сообщения чата и придумай "
        f"язвительный/смешной демотиватор по ситуации.\n\n"
        f"Сообщения чата:\n{history}\n"
        f"{examples_block}\n"
        f"Ответь строго в формате двух строк:\n"
        f"ЗАГОЛОВОК: <не более 5 слов, капслок не нужен>\n"
        f"ПОДПИСЬ: <не более 7 слов>\n\n"
        f"Только эти две строки, никакого другого текста."
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

    title    = await _shorten(title, max_words=5)
    subtitle = await _shorten(subtitle, max_words=7)

    if photo_file_id:
        photo_data = await _download_photo(message, photo_file_id)
        await wait.delete()
        await _send_demotivator_ai(message, photo_data, title, subtitle)
    else:
        await wait.edit_text(
            f"🤖 <b>{title.upper()}</b>\n<i>{subtitle}</i>\n\n"
            f"<i>💡 Фото из чата пока нет — пришли любую фотку!</i>",
            parse_mode="HTML",
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
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer("✓" if score["my_vote"] else "Голос снят")


# ─── S g a — анекдот ─────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Aa](\s+.+)?$"))
async def cmd_gen_joke(message: Message):
    if not await _check(message):
        return
    m = re.match(r"(?i)^[Ss]\s+[Gg]\s+[Aa](\s+(.+))?$", message.text)
    start = m.group(2).strip() if m.group(2) else ""
    wait = await message.reply("🤣 Генерирую анекдот...")
    history = _get_history(message.chat.id)
    joke = await _run_ai(ai.gen_joke, start, history)
    await wait.edit_text(f"🤣 {joke}")


# ─── Колбэки из панели ────────────────────────────────────────────────────────

@router.callback_query(F.data == "gen_text")
async def cb_gen_text(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.message.edit_text("✍️ Генерирую текст...")
    history = _get_history(call.message.chat.id)
    text = await _run_ai(ai.gen_text, "", 0, history)
    await call.message.edit_text(text)
    await call.answer()


@router.callback_query(F.data == "gen_word")
async def cb_gen_word(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    word = await _run_ai(ai.gen_word, 0)
    await call.message.edit_text(f"🔤 <b>{word}</b>", parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "gen_poll")
async def cb_gen_poll(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    from utils.history import get_poll_data
    data = get_poll_data(call.message.chat.id)
    if not data:
        await call.answer("❌ Недостаточно сообщений!", show_alert=True)
        return
    await call.message.delete()
    try:
        if data.get("is_quiz"):
            await call.message.answer_poll(
                question=data["question"],
                options=data["options"],
                type="quiz",
                correct_option_id=data.get("correct_option_id", 0),
                is_anonymous=False,
            )
        else:
            await call.message.answer_poll(
                question=data["question"],
                options=data["options"],
                is_anonymous=False,
            )
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {e}")
    await call.answer()


@router.callback_query(F.data == "gen_meme")
async def cb_gen_meme(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    template = random.choice(MEM_TEMPLATES)
    await call.message.edit_text("😂 Генерирую мем...")
    history = _get_history(call.message.chat.id)
    caption = await _run_ai(ai.gen_meme_caption, template, history)
    await call.message.edit_text(f"😂 <b>{template}</b>\n\n{caption}", parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "gen_demot")
async def cb_gen_demot(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.message.edit_text("🖼 Генерирую демотиватор...")
    from utils.history import get_two_random_messages
    title, subtitle = get_two_random_messages(call.message.chat.id)
    title    = await _shorten(title, max_words=5)
    subtitle = await _shorten(subtitle, max_words=7)
    await call.message.edit_text(
        f"🖼 <b>{title}</b>\n<i>{subtitle}</i>\n\n"
        f"<i>💡 Для картинки используй S g d с реплаем на фото</i>",
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "gen_demot_ai")
async def cb_gen_demot_ai(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.message.edit_text("🤖 Анализирую чат...")
    history = _get_history(call.message.chat.id)
    raw = await _run_ai(
        ai._ask,
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
    await call.message.edit_text(
        f"🤖 <b>{title.upper()}</b>\n<i>{subtitle}</i>\n\n"
        f"<i>💡 Для картинки используй S g d ai с реплаем на фото</i>",
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "gen_joke")
async def cb_gen_joke(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.message.edit_text("🤣 Генерирую анекдот...")
    history = _get_history(call.message.chat.id)
    joke = await _run_ai(ai.gen_joke, "", history)
    await call.message.edit_text(f"🤣 {joke}")
    await call.answer()


@router.callback_query(F.data == "gen_long")
async def cb_gen_long(call: CallbackQuery):
    if not await can_use_commands(call.message):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.message.edit_text("✍️ Генерирую длинный текст...")
    history = _get_history(call.message.chat.id)
    text = await _run_ai(ai.gen_long_text, history)
    await call.message.edit_text(text)
    await call.answer()


# ─── S g r — случайный реплай из истории чата ────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg]\s+[Rr]$"))
async def cmd_gen_reply(message: Message):
    if not await _check(message):
        return
    history = _get_history(message.chat.id)
    reply = await _run_ai(ai.gen_reply, history)
    await message.reply(reply)