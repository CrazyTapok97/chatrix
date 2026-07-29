"""
Обёртка над OpenRouter API.
AI использует только реальные сообщения из истории чата —
не придумывает текст, а выбирает и компонует фразы участников.
"""

from openai import AsyncOpenAI
import random
from config import OPENROUTER_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL, FALLBACK_MODELS, GROQ_MODELS, GOOGLE_MODELS
from utils.ai_updater import get_cached_models
from utils.ai_config import build_model_chain, clean_model_response, load_system_prompts, record_ai_result
from config import GOOGLE_MODELS
from utils.chat_style import style_instruction
from utils.settings_store import get_intelligence
from utils.history import get_random_message

import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_or_client = None
_groq_client = None
_google_client = None


def _get_or_client() -> AsyncOpenAI:
    global _or_client
    if _or_client is None:
        _or_client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY, 
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            default_headers={
                "HTTP-Referer": "https://github.com/Sgl-ypT5/Chatrix",
                "X-Title": "Chatrix Bot",
            }
        )
    return _or_client

def _get_groq_client() -> AsyncOpenAI:
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        _groq_client = AsyncOpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            max_retries=0
        )
    return _groq_client

def _get_google_client() -> AsyncOpenAI:
    global _google_client
    if _google_client is None and GOOGLE_API_KEY:
        _google_client = AsyncOpenAI(
            api_key=GOOGLE_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_retries=0
        )
    return _google_client


async def _ask(prompt: str, max_tokens: int = 400, image_url: str = None, sys_prompt: str = None, user_name: str = "") -> str:
    chain = build_model_chain()

    clients = {
        "groq": _get_groq_client,
        "google": _get_google_client,
        "openrouter": _get_or_client,
    }
    prompts = load_system_prompts()
    if sys_prompt is None:
        system_prompt = prompts.get("default", "Ты — Chatrix, полезный Telegram-ассистент.")
    else:
        system_prompt = sys_prompt
    if image_url:
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": f"{system_prompt}\n\n{prompt}"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

    if not chain:
        return "❌ AI-цепочка пуста. Проверь data/ai_config.json."

    for index, (provider, model) in enumerate(chain):
        getter = clients.get(provider)
        if getter is None:
            logger.warning("Unknown AI provider %s for model %s", provider, model)
            continue
        client = getter()
        if client is None:
            logger.warning("AI provider %s is not configured", provider)
            continue
        started = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                timeout=25.0 if image_url else 20.0,
            )
            elapsed = (time.monotonic() - started) * 1000
            content = clean_model_response(response.choices[0].message.content or "")
            if not content:
                record_ai_result(model, False, elapsed, fallback=index > 0)
                continue
            generic_responses = ["понял", "я понял", "понятно", "ясно", "ок", "окей", "хорошо", "ладно", "ага", "угу"]
            content_clean = content.lower().strip().rstrip(".!? \t")
            if content_clean in generic_responses:
                record_ai_result(model, False, elapsed, fallback=index > 0)
                continue
            record_ai_result(model, True, elapsed, fallback=index > 0)
            who = f" {user_name}:" if user_name else ":"
            logger.info("[AI] Ответил%s %s (%s)", who, model, provider)
            return content
        except Exception as exc:
            elapsed = (time.monotonic() - started) * 1000
            record_ai_result(model, False, elapsed, fallback=index > 0)
            logger.warning("AI model %s (%s) failed: %s", model, provider, exc)

    logger.error("All configured AI models failed, trying Google fallback")
    for model in GOOGLE_MODELS:
        client = _get_google_client()
        if client is None:
            continue
        started = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                timeout=25.0 if image_url else 20.0,
            )
            elapsed = (time.monotonic() - started) * 1000
            content = clean_model_response(response.choices[0].message.content or "")
            if not content:
                continue
            who = f" {user_name}:" if user_name else ":"
            logger.info("[AI] Ответил%s %s (google fallback)", who, model)
            return content
        except Exception as exc:
            logger.warning("Google fallback model %s failed: %s", model, exc)

    logger.error("All Google fallback models also failed")
    return "❌ Все настроенные AI-модели сейчас недоступны. Попробуй позже."

def _no_history_msg() -> str:
    return "❌ Недостаточно сообщений в чате — напишите побольше!"


# ─── Знания бота ─────────────────────────────────────────────────────────────

BOT_KNOWLEDGE = (
    "Ты — бот Чатрикс.\n\n"
    "Команды:\n"
    "/draw [описание] — рисует картинку. Флаги: --anime, --realistic, --art, --wide, --cinema, --poster.\n"
    "/redraw — перерисовывает последний /draw. Можно уточнить: /redraw добавь шляпу.\n"
    "/ask [вопрос] — прямой ответ ИИ.\n"
    "/search [запрос] / /wiki [тема] — поиск в интернете и сводка.\n"
    "/agent [задача] — разбивает сложную задачу на шаги.\n"
    "/vision, «анализ» — анализирует фото или текст.\n"
    "/tts [текст] — озвучивает текст.\n"
    "/plan [цель] — пошаговый план.\n"
    "/task /tasks — список задач.\n"
    "/set style [описание] — настроить стиль общения.\n"
    "/status — статус бота и чата.\n"
    "Развлечения: /rate, /roast, /fortune, /ship, /advice, /who.\n\n"
    "Если не хватает информации — используй [SEARCH] запрос [/SEARCH].\n"
    "Если просят продолжить (продолжай, дальше) — продолжай с того же места.\n"
    "Если прямо просят помощи, объяснения или инструкции (как сделать, покажи, помоги) — помогай, не груби."
)

# ─── Генерация текста ─────────────────────────────────────────────────────────

async def gen_text(start: str = "", length: int = 0, history: str = "") -> str:
    if not history:
        return _no_history_msg()
    if start:
        prompt = (
            f"{BOT_KNOWLEDGE}\n\n"
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя только фразы и слова из этой переписки, составь связный текст "
            f"начинающийся со слов: «{start}». "
            f"Используй реальные выражения участников. Только текст, без пояснений."
        )

    elif length:
        prompt = (
            f"{BOT_KNOWLEDGE}\n\n"
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя только фразы и слова из этой переписки, составь связный текст "
            f"длиной примерно {length} слов. "
            f"Используй реальные выражения участников. Только текст, без пояснений."
        )
    else:
        prompt = (
            f"{BOT_KNOWLEDGE}\n\n"
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя только фразы и слова из этой переписки, составь короткий связный текст (2–4 предложения). "
            f"Используй реальные выражения участников. Только текст, без пояснений."
        )
    return await _ask(prompt, max_tokens=600)


async def gen_long_text(history: str = "") -> str:
    if not history:
        return _no_history_msg()
    prompt = (
        f"{BOT_KNOWLEDGE}\n\n"
        f"Вот переписка из чата:\n{history}\n\n"
        f"Используя только фразы, темы и слова из этой переписки, составь длинный связный текст (10–15 предложений). "
        f"Используй реальные выражения участников. Только текст, без пояснений."
    )
    return await _ask(prompt, max_tokens=1200)


# ─── Генерация слова ──────────────────────────────────────────────────────────

async def gen_word(length: int = 0, history: str = "") -> str:
    if history:
        if length:
            prompt = (
                f"{BOT_KNOWLEDGE}\n\n"
                f"Вот переписка из чата:\n{history}\n\n"
                f"Выбери одно слово из этой переписки длиной ровно {length} букв. "
                f"Только слово, без пояснений."
            )
        else:
            prompt = (
                f"{BOT_KNOWLEDGE}\n\n"
                f"Вот переписка из чата:\n{history}\n\n"
                f"Выбери одно самое смешное или необычное слово из этой переписки. "
                f"Только слово, без пояснений."
            )
    else:
        if length:
            prompt = f"Придумай одно случайное русское слово длиной ровно {length} букв. Только слово."
        else:
            prompt = "Напиши одно случайное редкое или смешное русское слово. Только слово."
    return await _ask(prompt, max_tokens=30)


async def gen_poll_data(history: str = "", chat_id: int = 0) -> dict:
    """
    Абстрактный рандом: вместо осмысленных вопросов — эмодзи и обрывки фраз.
    Полный отказ от ИИ для этого типа контента.
    """
    from utils.history import get_history
    import random
    
    # Эмодзи для "вопроса"
    emojis = ["🌟", "😁", "🥰", "🤬", "🧐", "🤯", "👄", "😊", "❤️", "🌚", "💎", "🔥", "🌈", "🍄"]
    q_len = random.randint(1, 4)
    question = " ".join(random.sample(emojis, q_len))
    
    # Обрывки фраз для ответов
    msgs = get_history(chat_id, limit=300)
    if not msgs:
        return {"question": "???", "options": ["Да", "Нет", "Наверное", "База"], "is_quiz": False}
        
    # Собираем всё подряд: команды, обрывки, слова
    raw_pool = []
    for m in msgs:
        t = m["t"].strip()
        if len(t) > 1:
            raw_pool.append(t)
            
    # Добавляем эмодзи и в ответы
    raw_pool.extend(emojis)
    
    # Выбираем от 3 до 8 вариантов
    opt_count = random.randint(3, 8)
    if len(raw_pool) < opt_count:
        options = ["База", "Кринж", "Ауф"]
    else:
        options = random.sample(raw_pool, opt_count)
        
    # Обрезаем длину для лимитов Telegram (100 символов)
    options = [opt[:100] for opt in options]
    
    return {
        "question": question,
        "options": options,
        "is_quiz": False,
        "correct_option_id": 0
    }


# ─── Генерация анекдота ───────────────────────────────────────────────────────

async def gen_smart_reply(history: str = "", user_message: str = "", image_url: str = None, chat_id: int = None, web: str = None, user_name: str = "", reply_context: str = "") -> str:
    if not history:
        return _no_history_msg()

    if chat_id:
        mode = await get_intelligence(chat_id)
        if mode == "classic":
            phrase = get_random_message(chat_id)
            if phrase:
                return phrase

    custom_style = style_instruction(chat_id) if chat_id else ""
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    parts = [BOT_KNOWLEDGE, f"\n\nСегодня {now_str}.\n\n"]
    if reply_context:
        if reply_context.startswith("Пользователь спросил:"):
            parts.append("{}\n\n".format(reply_context))
            parts.append("Пользователь просит продолжить: \"{}\"\n\n".format(user_message))
            parts.append("Продолжи свою мысль с того места, где остановился. Не повторяй уже написанное. ")
        else:
            parts.append("Ты ранее написал: \"{}\"\n\n".format(reply_context))
            parts.append("Пользователь отвечает на это: \"{}\"\n\n".format(user_message))
            parts.append("Продолжи свою мысль, используя контекст выше. ")
    else:
        parts.append("Вот контекст переписки:\n{}\n\n".format(history))
        parts.append("Последнее сообщение: \"{}\"\n\n".format(user_message))
        parts.append("Ответь на это сообщение, используя свои знания о себе и стиль общения участников чата. ")
    if image_url:
        parts.append("Учти изображение, которое прислал пользователь. ")
    if web:
        parts.append("Вот актуальная информация из интернета — используй её в ответе:\n{}\n".format(web))
    parts.append("Твой ответ должен быть осмысленным, но в духе этого сообщества. ")
    parts.append("Не предлагай помощь, советы или разъяснения, если тебя об этом не попросили. Ты участник чата, а не техподдержка. Если тебе грубят — можешь ответить грубо или с иронией. ")
    parts.append("Только если демотиватор ОЧЕНЬ уместен к ситуации, используй формат: [DEMOT] описание картинки на русском | ЗАГОЛОВОК КАПС | подпись [/DEMOT]. Не делай демотиватор без причины. ")
    parts.append("ВАЖНО: Ты НЕ ЗНАЕШЬ актуальные адреса, телефоны, цены, рейтинги, названия заведений и режим работы. Если вопрос про конкретные места, магазины, услуги, адреса или контакты — НЕ ВЫДУМЫВАЙ. Напиши только [SEARCH] запрос [/SEARCH] и больше ничего. Дождись результатов поиска. ")
    parts.append("Используй информацию из истории, если это уместно. Только текст ответа.")
    prompt = "".join(parts)
    sys_prompt = custom_style if custom_style else None
    return await _ask(prompt, max_tokens=1200, image_url=image_url, sys_prompt=sys_prompt, user_name=user_name)


async def gen_joke(start: str = "", history: str = "") -> str:
    if not history:
        return _no_history_msg()
    if start:
        prompt = (
            f"{BOT_KNOWLEDGE}\n\n"
            f"Вот переписка из чата:\n{history}\n\n"
            f"Составь смешной анекдот, используя реальные фразы, имена и локальные мемы из этой переписки. "
            f"Анекдот должен начинаться со слов: «{start}». Только анекдот."
        )
    else:
        prompt = (
            f"{BOT_KNOWLEDGE}\n\n"
            f"Вот переписка из чата:\n{history}\n\n"
            f"Проанализируй темы обсуждения и участников. "
            f"Составь актуальный и смешной анекдот про участников и текущие события в чате. "
            f"Используй локальные шутки и имена. Только анекдот."
        )
    return await _ask(prompt, max_tokens=600)


# ─── Мем-подпись ─────────────────────────────────────────────────────────────

async def gen_meme_caption(template: str = "", history: str = "") -> tuple[str, str]:
    if not history:
        return "ПУСТО", "..."
    if template:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя ТОЛЬКО реальные фразы из этой переписки, придумай смешной текст для мема на тему: «{template}». "
            f"Выбери две фразы: одну для заголовка (короткая) и одну для подписи. "
            f"Ответь строго в формате JSON без markdown:\n"
            '{"title": "ФРАЗА ИЗ ЧАТА", "subtitle": "другая фраза из чата"}'
        )
    else:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Придумай тему и смешной текст для мема на основе этой переписки. "
            f"Выбери две фразы: одну для заголовка (короткая, тема мема) и одну для подписи. "
            f"Ответь строго в формате JSON без markdown:\n"
            '{"title": "ТЕМА МЕМА", "subtitle": "фраза из чата"}'
        )
    import json, re
    raw = await _ask(prompt, max_tokens=150)
    if "Ошибка" in raw or not raw:
        return template or "МЕМ", "..."
        
    raw = re.sub(r"```[a-z]*", "", raw).strip().strip("`")
    try:
        d = json.loads(raw)
        return d["title"], d["subtitle"]
    except Exception:
        return template or "МЕМ", "..."


async def gen_demot_data(history: str = "", chat_id: int = 0) -> tuple[str, str]:
    def _fallback():
        from utils.history import get_two_random_messages
        return get_two_random_messages(chat_id)

    if not history:
        return _fallback()
        
    # Перемешиваем строки чтобы каждый раз был разный результат
    lines = history.strip().split("\n")
    random.shuffle(lines)
    history = "\n".join(lines)
    prompt = (
        f"Вот переписка из чата:\n{history}\n\n"
        f"Выбери случайные фразы из этой переписки для демотиватора. "
        f"Каждый раз выбирай разные фразы. "
        f"Заголовок и подпись должны быть реальными цитатами из чата. "
        "Ответь строго в формате JSON без markdown:\n"
        '{"title": "ФРАЗА ИЗ ЧАТА CAPS", "subtitle": "другая фраза из чата строчными"}'
    )
    import json, re
    raw = await _ask(prompt, max_tokens=150)
    if "Ошибка" in raw or not raw:
        return _fallback()
        
    raw = re.sub(r"```[a-z]*", "", raw).strip().strip("`")
    try:
        d = json.loads(raw)
        return d["title"], d["subtitle"]
    except Exception:
        return _fallback()


async def gen_business_reply(user_full_name: str, user_message: str, image_url: str = None, chat_id: int = None) -> str:
    if chat_id:
        mode = await get_intelligence(chat_id)
        if mode == "classic":
            phrase = get_random_message(chat_id)
            if phrase:
                return phrase

    custom_style = style_instruction(chat_id) if chat_id else ""
    if custom_style:
        sys_prompt = custom_style
        prompt = (
            f"{BOT_KNOWLEDGE}\n\n"
            f"Тебе пришло сообщение от {user_full_name}: \"{user_message}\".\n\n"
            f"{'Пользователь также прикрепил изображение. ' if image_url else ''}"
            f"Только текст ответа, без пояснений."
        )
    else:
        sys_prompt = None
        prompt = (
            f"{BOT_KNOWLEDGE}\n"
            f"Ты — владелец этого аккаунта. Тебе пришло сообщение от {user_full_name}: \"{user_message}\".\n\n"
            f"{'Пользователь также прикрепил изображение. ' if image_url else ''}"
            f"Отвечай от первого лица, как человек. "
            f"Ни в коем случае не упоминай, что ты ИИ или ассистент.\n"
            f"Если спрашивают про Чатрикса (тебя) — можешь вскользь упомянуть свои функции из знаний выше, как будто ты сам это умеешь/делаешь.\n"
            f"Ты адаптивен: подстраиваешь стиль под пользователя.\n"
            f"Если пользователь шутит — шутишь.\n"
            f"Если серьезный — отвечаешь строго.\n"
            f"Всегда даешь полезную информацию.\n"
            f"Не повторяешься и не задаешь тупых вопросов.\n\n"
            f"Только текст ответа, без пояснений."
        )
    return await _ask(prompt, max_tokens=4096, image_url=image_url, sys_prompt=sys_prompt, user_name=user_full_name)


# ─── Случайный реплай ────────────────────────────────────────────────────────

async def gen_reply(history: str = "") -> str:
    if not history:
        return _no_history_msg()
    prompt = (
        f"Вот переписка из чата:\n{history}\n\n"
        f"Выбери одну случайную фразу или сообщение из этой переписки и верни её как есть, "
        f"без изменений. Только фраза, ничего лишнего."
    )
    return await _ask(prompt, max_tokens=100)