import re
import logging

logger = logging.getLogger(__name__)

_name_cache = {}

TRANSLIT_MAP = {
    'shch': 'щ', 'sh': 'ш', 'ch': 'ч', 'zh': 'ж', 'yo': 'ё', 'yu': 'ю', 'ya': 'я',
    'kh': 'х', 'ts': 'ц', 'ee': 'и', 'oo': 'у', 'qu': 'кв',
    'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е', 'z': 'з',
    'i': 'и', 'j': 'й', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о',
    'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'f': 'ф', 'y': 'ы',
    'x': 'кс', 'w': 'в', 'q': 'к',
}


def translit_to_cyr(text: str) -> str:
    if not text:
        return text
    if re.search('[а-яА-Я]', text):
        return text
    res = text.lower()
    for k, v in TRANSLIT_MAP.items():
        if len(k) > 1:
            res = res.replace(k, v)
    for k, v in TRANSLIT_MAP.items():
        if len(k) == 1:
            res = res.replace(k, v)
    return res.capitalize()


async def get_name(event_or_bot, uid: int) -> str:
    if uid in _name_cache:
        return _name_cache[uid]
    try:
        chat = await event_or_bot.get_chat(uid)
        name = getattr(chat, "first_name", None) or getattr(chat, "title", None) or f"User {uid}"
    except Exception:
        name = f"User {uid}"
    name = translit_to_cyr(name)
    _name_cache[uid] = name
    return name


def clear_name_cache():
    _name_cache.clear()
