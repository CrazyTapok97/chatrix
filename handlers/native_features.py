import asyncio
import base64
import os
import random
import re
from collections import Counter

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from utils.ai_updater import get_cached_models, update_models_cache
from utils.history import format_history, get_history
from utils.settings_store import get_laziness
from utils.access import is_admin
from utils.chat_style import get_chat_settings, update_chat_setting, style_instruction
from utils.ai_config import detect_provider, load_ai_config, save_ai_config
from config import ADMIN_IDS
from utils.native_features import (
    add_task,
    ask_ai,
    chat_top,
    generate_image,
    load_tasks,
    model_report,
    parse_ship_pair,
    run_agent,
    synthesize_speech,
    web_search,
)
from utils.antispam import is_ratelimited

router = Router()
_last_draw_prompt: dict[int, str] = {}



def _argument(message: Message) -> str:
    text = message.text or message.caption or ""
    return text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) > 1 else ""


async def _reply(message: Message, text: str):
    return await message.bot.send_message(
        message.chat.id,
        text[:4096],
        reply_to_message_id=message.message_id,
        business_connection_id=message.business_connection_id,
    )


@router.message(Command("help"))
async def command_help(message: Message):
    await _reply(message, (
        "✨ ОСНОВНЫЕ КОМАНДЫ\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💬 /ask [вопрос] — прямой вопрос ИИ\n"
        "🔍 /search [запрос] — поиск и сводка\n"
        "📖 /wiki [тема] — справка из Википедии\n"
        "🤖 /agent [задача] — многошаговый AI-ответ\n"
        "🎙 /tts [текст] — озвучить текст или реплай\n"
        "🖼 /vision, «анализ» — анализ текста, медиа или стикера\n"
        "🎨 /draw [описание] — нарисовать изображение\n"
"🔄 /redraw — перерисовать последний /draw (улучшенная версия)\n"
        "📋 /status — текущий статус бота\n"
        "📊 /top, /stats — активность чата\n"
        "🎮 /fun, /rate, /roast, /fortune, /ship, /advice, /who\n\n"
        "⚙️ НАСТРОЙКИ И ГЕНЕРАЦИЯ\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "S c — настройки чата\n"
        "/set style|vstyle|group|chance|mode [значение]\n"
        "S g — генерация текста; S g w — слово; S g p — опрос\n"
        "S g m — мем; S g d — демотиватор; S g d ai — AI-демотиватор\n"
        "S g a — анекдот; S g s — стикер; S g l — длинный текст\n\n"
        "🎲 МАФИЯ\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/mafia — создать игру; /helpmafia — все правила\n"
        "/mstatus — статус партии; /players — игроки; /role — моя роль\n\n"
        "🔑 АДМИН\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/models, /model_health — модели ИИ\n"
        "/backup — резервная копия; /addmeme — добавить шаблон\n"
        "/autostatus, /testauto — автоконтент; S index — индексировать мемы"
    ))

@router.message(Command("models"))
async def command_models(message: Message):
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await _reply(message, "Команда доступна только администратору.")
        return
    requested = _argument(message)
    if requested:
        config = load_ai_config()
        provider = detect_provider(requested, get_cached_models() or {})
        config["primary_model"] = requested
        config["primary_provider"] = provider
        config["primary_model_changed_at"] = __import__("time").time()
        save_ai_config(config)
        await _reply(message, f"Основная модель: {requested}\nПровайдер: {provider}")
        return
    await _reply(message, model_report())


@router.message(Command("model_health"))
async def command_model_health(message: Message):
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await _reply(message, "Команда доступна только администратору.")
        return
    status = await _reply(message, "Проверяю модели…")
    await update_models_cache()
    result = await ask_ai("Ответь одним словом: работает", 10)
    await status.edit_text(f"Модели обновлены. Тестовый ответ: {result[:100]}")


@router.message(Command("status"))
async def command_status(message: Message):
    config = load_ai_config()
    settings = get_chat_settings(message.chat.id)
    history = get_history(message.chat.id)
    chat_types = {
        "private": "Личные сообщения",
        "group": "Группа",
        "supergroup": "Супергруппа",
        "channel": "Канал",
    }
    style = settings.get("prompt") or "Стандартный адаптивный стиль"
    if len(style) > 700:
        style = style[:697] + "…"
    reply_every = max(1, int(settings.get("reply_every", 10)))
    progress = len(history) % reply_every or reply_every
    sticker_chance = round(float(settings.get("sticker_chance", 0.5)) * 100)
    laziness = await get_laziness(message.chat.id)
    admin = "да" if await is_admin(message) else "нет"
    await _reply(message, (
        "📋 СТАТУС\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 ИИ: 🟢 АКТИВЕН\n"
        f"🧠 Модель: {config.get('primary_model', 'не настроена')}\n"
        f"📍 Чат: {message.chat.id} ({chat_types.get(message.chat.type, message.chat.type)})\n"
        f"👤 Стиль: {style}\n"
        f"📊 Счётчик: {progress}/{reply_every}\n"
        f"💬 Лень: {laziness}%\n"
        f"🎲 Стикеры: {sticker_chance}%\n"
        f"🔑 Админ: {admin}"
    ))

@router.message(Command("ask"))
async def command_ask(message: Message):
    query = _argument(message)
    if not query:
        await _reply(message, "Формат: /ask вопрос")
        return
    await message.bot.send_chat_action(message.chat.id, "typing")
    await _reply(message, await ask_ai(query, 900))


@router.message(Command("agent"))
async def command_agent(message: Message):
    query = _argument(message)
    if not query:
        await _reply(message, "Формат: /agent сложная задача")
        return
    progress = await _reply(message, "Агент планирует и выполняет задачу…")
    result = await run_agent(query)
    await progress.edit_text(result[:4096])


async def _search_and_summarize(message: Message, wiki: bool = False):
    query = _argument(message)
    if not query:
        await _reply(message, "Добавь поисковый запрос после команды.")
        return
    search_query = f"site:ru.wikipedia.org {query}" if wiki else query
    try:
        results = await web_search(search_query)
    except Exception as exc:
        await _reply(message, f"Ошибка поиска: {exc}")
        return
    if not results:
        await _reply(message, "Ничего не найдено.")
        return
    context = "\n\n".join(
        f"{item.get('title', '')}\n{item.get('body', '')}\n{item.get('href', item.get('url', ''))}"
        for item in results
    )
    prompt = (
        f"Сделай точную краткую справку по запросу «{query}» на основе результатов ниже. "
        "Не выдумывай факты и в конце перечисли найденные ссылки.\n\n" + context
    )
    await _reply(message, await ask_ai(prompt, 1000))


@router.message(Command("search"))
async def command_search(message: Message):
    await _search_and_summarize(message)


@router.message(Command("wiki"))
async def command_wiki(message: Message):
    await _search_and_summarize(message, wiki=True)


@router.message(Command("draw"))
async def command_draw(message: Message):
    prompt = _argument(message)
    if not prompt:
        await _reply(message, "Формат: /draw кот в космосе --wide --anime")
        return
    progress = await _reply(message, "Рисую…")
    try:
        image = await generate_image(prompt)
        await message.bot.send_photo(
            message.chat.id,
            BufferedInputFile(image, filename="chatrix.jpg"),
            caption=f"Запрос: {prompt[:900]}",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id,
        )
        await progress.delete()
        _last_draw_prompt[message.chat.id] = prompt
    except Exception as exc:
        await progress.edit_text(f"Не удалось нарисовать: {exc}")


@router.message(Command("redraw"))
async def command_redraw(message: Message):
    prompt = _last_draw_prompt.get(message.chat.id)
    if not prompt and message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot:
        cap = (message.reply_to_message.caption or "").strip()
        for prefix in ("Запрос: ", "Перерисовано: "):
            if cap.startswith(prefix):
                prompt = cap[len(prefix):]
                break
    if not prompt:
        await _reply(message, "Ответь /redraw на фото которое бот нарисовал, или сначала используй /draw.")
        return
    addition = _argument(message)
    if addition:
        prompt = f"{prompt}, {addition}"
    _last_draw_prompt[message.chat.id] = prompt
    progress = await _reply(message, "Перерисовываю…")
    try:
        image = await generate_image(prompt, redraw=True)
        await message.bot.send_photo(
            message.chat.id,
            BufferedInputFile(image, filename="chatrix_redraw.jpg"),
            caption=f"Перерисовано: {prompt[:900]}",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id,
        )
        await progress.delete()
    except Exception as exc:
        await progress.edit_text(f"Не удалось перерисовать: {exc}")


@router.message(Command("vision"))
async def command_vision(message: Message):
    await _analyze(message, _argument(message))


@router.message(F.text.regexp(r"(?iu)^\s*(?:анализ|анализируй|проанализируй)(?:\s+.*)?$"))
@router.message(F.caption.regexp(r"(?iu)^\s*(?:анализ|анализируй|проанализируй)(?:\s+.*)?$"))
async def command_analysis_alias(message: Message):
    content = message.text or message.caption or ""
    prompt = re.sub(r"(?iu)^\s*(?:анализ|анализируй|проанализируй)\s*", "", content).strip()
    await _analyze(message, prompt)


def _visual_file(source: Message) -> tuple[str | None, str | None]:
    if source.photo:
        return source.photo[-1].file_id, "image/jpeg"
    if source.sticker:
        sticker = source.sticker
        if not sticker.is_animated and not sticker.is_video:
            return sticker.file_id, "image/webp"
        if sticker.thumbnail:
            return sticker.thumbnail.file_id, "image/jpeg"
    if source.animation and source.animation.thumbnail:
        return source.animation.thumbnail.file_id, "image/jpeg"
    if source.video and source.video.thumbnail:
        return source.video.thumbnail.file_id, "image/jpeg"
    if source.document and (source.document.mime_type or "").startswith("image/"):
        return source.document.file_id, source.document.mime_type
    return None, None


async def _analyze(message: Message, prompt: str):
    source = message.reply_to_message or message
    chat_history = format_history(message.chat.id, limit=2)
    history_block = f"Вот контекст переписки:\n{chat_history}\n\n" if chat_history else ""
    style_prompt = style_instruction(message.chat.id)

    file_id, mime_type = _visual_file(source)
    if file_id:
        try:
            file = await message.bot.get_file(file_id)
            stream = await message.bot.download_file(file.file_path)
            encoded = base64.b64encode(stream.read()).decode("ascii")
            source_text = (source.text or source.caption or "").strip()
            msg = f"{history_block}Коротко (до 30 слов) опиши что на этом фото. {source_text}"
            request = prompt or msg
            await _reply(message, await ask_ai(request, 1000, f"data:{mime_type};base64,{encoded}", sys_prompt=style_prompt))
        except Exception as exc:
            await _reply(message, f"Ошибка анализа медиа: {exc}")
        return

    target_text = ""
    if source is not message:
        target_text = source.text or source.caption or ""
    elif prompt:
        target_text = prompt
    if not target_text:
        await _reply(message, "Добавь текст, прикрепи медиа или ответь на сообщение командой /vision либо словом «анализ».")
        return
    request = f"{history_block}Коротко ответь на это. Без формальностей:\n\n{target_text}"
    if prompt and source is not message:
        request = f"{history_block}{prompt}\n\n{target_text}"
    await _reply(message, await ask_ai(request, 1000, sys_prompt=style_prompt))

@router.message(Command("tts"))
async def command_tts(message: Message):
    text = _argument(message)
    if not text and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not text:
        await _reply(message, "Формат: /tts текст — или ответь командой на сообщение.")
        return
    try:
        audio = await synthesize_speech(text)
        await message.bot.send_voice(
            message.chat.id,
            BufferedInputFile(audio, filename="speech.mp3"),
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id,
        )
    except Exception as exc:
        await _reply(message, f"Ошибка озвучки: {exc}")


@router.message(Command("plan"))
async def command_plan(message: Message):
    goal = _argument(message)
    if not goal:
        await _reply(message, "Формат: /plan цель")
        return
    await _reply(message, await ask_ai(f"Составь практичный пошаговый план достижения цели: {goal}", 800))


@router.message(Command("task"))
async def command_task(message: Message):
    task = _argument(message)
    if not task or not message.from_user:
        await _reply(message, "Формат: /task текст задачи")
        return
    tasks = add_task(message.from_user.id, task, message.chat.id)
    await _reply(message, f"Задача добавлена. Всего активных задач: {len(tasks)}")


@router.message(Command("tasks"))
async def command_tasks(message: Message):
    tasks = load_tasks(message.from_user.id) if message.from_user else []
    if not tasks:
        await _reply(message, "Список задач пуст. Добавление: /task текст")
        return
    await _reply(message, "Задачи:\n" + "\n".join(f"{index}. {task}" for index, task in enumerate(tasks, 1)))


@router.message(Command("rate"))
async def command_rate(message: Message):
    target = _argument(message) or "это"
    score = random.randint(0, 100)
    comment = await ask_ai(f"Оцени «{target}» на {score}/100 одной короткой саркастичной фразой.", 100)
    await _reply(message, f"{target}: {score}/100\n{comment}")


@router.message(Command("roast"))
async def command_roast(message: Message):
    target = _argument(message) or (message.from_user.full_name if message.from_user else "меня")
    await _reply(message, await ask_ai(f"Придумай остроумный, но не жестокий roast про {target}. Одна фраза.", 120))


@router.message(Command("fortune"))
async def command_fortune(message: Message):
    area = _argument(message) or random.choice(["любовь", "деньги", "работа", "удача", "ближайшие сутки"])
    name = message.from_user.full_name if message.from_user else "пользователь"
    result = await ask_ai(f"Дай мистическое и слегка ироничное предсказание для {name} по теме «{area}», до 30 слов.", 120)
    await _reply(message, f"Предсказание — {area}:\n{result}")


@router.message(Command("ship"))
async def command_ship(message: Message):
    try:
        first, second = parse_ship_pair(_argument(message))
    except ValueError as exc:
        await _reply(message, str(exc))
        return
    score = random.randint(0, 100)
    comment = await ask_ai(f"Совместимость {first} и {second}: {score}%. Одна смешная фраза.", 100)
    await _reply(message, f"{first} + {second}: {score}%\n{comment}")


@router.message(Command("advice"))
async def command_advice(message: Message):
    target = _argument(message) or (message.from_user.full_name if message.from_user else "пользователь")
    await _reply(message, await ask_ai(f"Дай {target} короткий полезный жизненный совет с лёгкой иронией.", 120))


@router.message(Command("who"))
async def command_who(message: Message):
    question = _argument(message)
    names = [item.get("u") for item in get_history(message.chat.id) if item.get("u")]
    if not question or not names:
        await _reply(message, "Формат: /who самый весёлый — нужна история чата.")
        return
    winner = random.choice(names)
    comment = await ask_ai(f"Вопрос: кто {question}? Выбран {winner}. Объясни одной шуточной фразой.", 100)
    await _reply(message, f"{question}: {winner}\n{comment}")


@router.message(Command("top", "stats"))
async def command_top(message: Message):
    top = chat_top(message.chat.id)
    if not top:
        await _reply(message, "Пока недостаточно истории сообщений.")
        return
    await _reply(message, "Активность чата:\n" + "\n".join(
        f"{index}. {name} — {count}" for index, (name, count) in enumerate(top, 1)
    ))


@router.message(Command("set"))
async def command_set(message: Message):
    args = _argument(message)
    if not args:
        current = style_instruction(message.chat.id)
        label = current if current else "(не задан)"
        await _reply(message, f"Текущий стиль: {label}\n\nФормат: /set style <описание стиля>\n/set vstyle, /set group, /set chance, /set mode")
        return
    parts = args.split(maxsplit=1)
    name = parts[0]
    value = parts[1] if len(parts) > 1 else ""
    try:
        key, normalized = update_chat_setting(message.chat.id, name, value)
        await _reply(message, f"✅ Настройка {key} = {normalized}")
    except ValueError as e:
        await _reply(message, f"❌ {e}")


@router.message(Command("fun"))
async def command_fun(message: Message):
    await _reply(message, "Развлечения: /rate, /roast, /fortune, /ship, /advice, /who")


@router.message(Command("backup"))
async def command_backup(message: Message):
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await _reply(message, "Только для администратора.")
        return
    await _reply(message, "⏳ Создаю бэкап...")
    try:
        from utils.backups import create_backup
        path = await asyncio.to_thread(create_backup)
        if path:
            with open(path, "rb") as f:
                await message.bot.send_document(
                    chat_id=message.chat.id,
                    document=f,
                    caption=f"💾 **Ручной бэкап**",
                    reply_to_message_id=message.message_id,
                )
        else:
            await _reply(message, "❌ Ошибка создания бэкапа.")
    except Exception as e:
        await _reply(message, f"❌ Ошибка: {e}")
BUSINESS_COMMANDS = {
    "help": command_help,
    "models": command_models,
    "model_health": command_model_health,
    "ask": command_ask,
    "agent": command_agent,
    "search": command_search,
    "wiki": command_wiki,
    "draw": command_draw,
    "redraw": command_redraw,
    "vision": command_vision,
    "status": command_status,
    "tts": command_tts,
"plan": command_plan,
    "task": command_task,
    "tasks": command_tasks,
    "rate": command_rate,
    "roast": command_roast,
    "fortune": command_fortune,
    "ship": command_ship,
    "advice": command_advice,
    "who": command_who,
    "top": command_top,
    "stats": command_top,
    "fun": command_fun,
    "set": command_set,
    "backup": command_backup,
}


async def dispatch_business_command(message: Message) -> bool:
    text = (message.text or message.caption or "").strip()
    if not text.startswith("/"):
        return False
    command = text[1:].split(maxsplit=1)[0].split("@", 1)[0].lower()
    handler = BUSINESS_COMMANDS.get(command)
    if handler is None:
        return False
    await handler(message)
    return True
