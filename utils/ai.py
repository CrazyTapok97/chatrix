"""
Обёртка над OpenRouter API.
AI использует только реальные сообщения из истории чата —
не придумывает текст, а выбирает и компонует фразы участников.
"""

from openai import OpenAI
import random
from config import OPENROUTER_API_KEY, GEMINI_MODEL, FALLBACK_MODELS

_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


def _ask(prompt: str, max_tokens: int = 400) -> str:
    for model in FALLBACK_MODELS:
        try:
            response = _client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            if not content:
                continue
            return content.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower() or "unavailable" in err.lower():
                continue
            return f"❌ Ошибка генерации: {e}"
    return "❌ Все модели перегружены, попробуй позже"


def _no_history_msg() -> str:
    return "❌ Недостаточно сообщений в чате — напишите побольше!"


# ─── Генерация текста ─────────────────────────────────────────────────────────

def gen_text(start: str = "", length: int = 0, history: str = "") -> str:
    if not history:
        return _no_history_msg()
    if start:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя только фразы и слова из этой переписки, составь связный текст "
            f"начинающийся со слов: «{start}». "
            f"Используй реальные выражения участников. Только текст, без пояснений."
        )
    elif length:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя только фразы и слова из этой переписки, составь связный текст "
            f"длиной примерно {length} слов. "
            f"Используй реальные выражения участников. Только текст, без пояснений."
        )
    else:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя только фразы и слова из этой переписки, составь короткий связный текст (2–4 предложения). "
            f"Используй реальные выражения участников. Только текст, без пояснений."
        )
    return _ask(prompt, max_tokens=600)


def gen_long_text(history: str = "") -> str:
    if not history:
        return _no_history_msg()
    prompt = (
        f"Вот переписка из чата:\n{history}\n\n"
        f"Используя только фразы, темы и слова из этой переписки, составь длинный связный текст (10–15 предложений). "
        f"Используй реальные выражения участников. Только текст, без пояснений."
    )
    return _ask(prompt, max_tokens=1200)


# ─── Генерация слова ──────────────────────────────────────────────────────────

def gen_word(length: int = 0, history: str = "") -> str:
    if history:
        if length:
            prompt = (
                f"Вот переписка из чата:\n{history}\n\n"
                f"Выбери одно слово из этой переписки длиной ровно {length} букв. "
                f"Только слово, без пояснений."
            )
        else:
            prompt = (
                f"Вот переписка из чата:\n{history}\n\n"
                f"Выбери одно самое смешное или необычное слово из этой переписки. "
                f"Только слово, без пояснений."
            )
    else:
        if length:
            prompt = f"Придумай одно случайное русское слово длиной ровно {length} букв. Только слово."
        else:
            prompt = "Напиши одно случайное редкое или смешное русское слово. Только слово."
    return _ask(prompt, max_tokens=30)



    prompt = (
        f"Вот переписка из чата:\n{history}\n\n"
        f"На основе ТОЛЬКО реальных тем, фраз и событий из этой переписки придумай вопрос для Telegram-опроса. "
        f"Варианты ответов тоже должны быть основаны на реальных фразах или именах из переписки. "
        "Ответь строго в формате JSON без markdown:\n"
        '{"question": "...", "options": ["...", "...", "...", "..."], '
        '"is_quiz": false, "correct_option_id": 0}'
    )
    import json, re
    raw = _ask(prompt, max_tokens=300)
    raw = re.sub(r"```[a-z]*", "", raw).strip().strip("`")
    try:
        return json.loads(raw)
    except Exception:
        return {
            "question": "Что важнее?",
            "options": ["Кофе", "Сон", "Код", "Пицца"],
            "is_quiz": False,
            "correct_option_id": 0,
        }


# ─── Генерация анекдота ───────────────────────────────────────────────────────

def gen_joke(start: str = "", history: str = "") -> str:
    if not history:
        return _no_history_msg()
    if start:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя реальные фразы, имена и темы из этой переписки, "
            f"составь смешной анекдот начинающийся со слов: «{start}». Только анекдот."
        )
    else:
        prompt = (
            f"Вот переписка из чата:\n{history}\n\n"
            f"Используя реальные фразы, имена и темы из этой переписки, "
            f"составь смешной анекдот про участников чата. Только анекдот."
        )
    return _ask(prompt, max_tokens=400)


# ─── Мем-подпись ─────────────────────────────────────────────────────────────

def gen_meme_caption(template: str, history: str = "") -> str:
    if not history:
        return template
    prompt = (
        f"Вот переписка из чата:\n{history}\n\n"
        f"Используя реальные фразы из этой переписки, придумай смешную подпись для мема на тему: «{template}». "
        f"Подпись должна содержать реальные выражения участников чата. Одна-две строки, только текст."
    )
    return _ask(prompt, max_tokens=100)


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
    raw = _ask(prompt, max_tokens=150)
    raw = re.sub(r"```[a-z]*", "", raw).strip().strip("`")
    try:
        d = json.loads(raw)
        return d["title"], d["subtitle"]
    except Exception:
        return "ЖИЗНЬ", "она такая"


# ─── Случайный реплай ────────────────────────────────────────────────────────

def gen_reply(history: str = "") -> str:
    if not history:
        return _no_history_msg()
    prompt = (
        f"Вот переписка из чата:\n{history}\n\n"
        f"Выбери одну случайную фразу или сообщение из этой переписки и верни её как есть, "
        f"без изменений. Только фраза, ничего лишнего."
    )
    return _ask(prompt, max_tokens=100)