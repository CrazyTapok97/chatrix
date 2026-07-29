import asyncio
import logging
import random
import re

import requests
from datetime import datetime

logger = logging.getLogger(__name__)

WEATHER_LAT = 52.2873
WEATHER_LON = 76.9674
WEATHER_CITY = "Павлодар"

WEATHER_CODES = {
    0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность", 3: "Пасмурно",
    45: "Туман", 48: "Туман с инеем", 51: "Лёгкая морось", 53: "Морось", 55: "Сильная морось",
    61: "Лёгкий дождь", 63: "Дождь", 65: "Сильный дождь", 71: "Лёгкий снег",
    73: "Снег", 75: "Сильный снег", 77: "Снежная крупа", 80: "Ливень",
    81: "Ливни", 82: "Сильный ливень", 85: "Снегопад", 86: "Сильный снегопад",
    95: "Гроза", 96: "Гроза с градом", 99: "Гроза с сильным градом",
}

WEATHER_ICONS = {
    0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️", 45: "🌫", 48: "🌫",
    51: "🌧", 53: "🌧", 55: "🌧", 61: "🌧", 63: "🌧", 65: "🌧",
    71: "🌨", 73: "🌨", 75: "🌨", 77: "🌨", 80: "⛈", 81: "⛈",
    82: "⛈", 85: "🌨", 86: "🌨", 95: "⛈", 96: "⛈", 99: "⛈",
}


def _normalize(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_weather_intent(user_message: str) -> bool:
    text = _normalize(user_message)
    if not text:
        return False

    original = (user_message or "").lower()
    has_question_mark = "?" in original

    technical_terms = ("cpu", "gpu", "процессор", "видеокарт", "сервер", "комп",
                       "компьютер", "ноутбук", "пк", "желез")
    if any(term in text for term in technical_terms):
        return False

    condition_terms = ("дожд", "снег", "ветер", "жарко", "холодно", "мороз", "зонт")

    direct = (
        r"^(?:мамбо\s+)?погода$",
        r"\bсколько\s+градус",
        r"\bкак(?:ая|ой|ую)?\s+(?:(?:сейчас|там|сегодня|завтра|на\s+улице|у\s+нас)\s+)?погод",
        r"\bчто\s+(?:по|с)\s+погод",
        r"\bпогода\s+(?:сейчас|сегодня|завтра|вечером|утром)\b",
        r"\b(?:скажи|покажи|глянь|узнай|дай|напиши|расскажи)\s+(?:мне\s+)?(?:погоду|прогноз)",
        r"\bпрогноз\s+(?:погоды|на\s+сегодня|на\s+завтра)?\b",
        r"\bтемпература\s+(?:сейчас|на\s+улице|за\s+окном)\b",
        r"\bчто\s+(?:там\s+)?(?:на\s+улице|за\s+окном)\b",
        r"\bкак\s+(?:там\s+)?(?:на\s+улице|за\s+окном)\b",
        r"\b(?:брать|нужен|нужна)\s+зонт\b",
        r"\bзонт\s+(?:брать|нужен|нужна)\b",
        r"\bчто\s+надеть\s+(?:на\s+улицу|сегодня|завтра)\b",
        r"\b(?:дождь|снег)\s+будет\b",
        r"\bбудет\s+(?:дождь|снег)\b",
    )
    if any(re.search(p, text) for p in direct):
        return True

    has_condition = any(term in text for term in condition_terms)
    if has_condition and has_question_mark and len(text.split()) <= 10:
        return True

    return False


def has_time_intent(user_message: str) -> bool:
    text = _normalize(user_message)
    keywords = ["который час", "сколько время", "время сейчас", "часы показывают"]
    return any(kw in text for kw in keywords)


def has_math_intent(user_message: str) -> bool:
    text = _normalize(user_message)
    keywords = ["посчитай", "сколько будет", "сколько получится", "вычисли", "калькулятор"]
    return any(kw in text for kw in keywords)


async def get_weather() -> str | None:
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               f"?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
               "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
               "&wind_speed_unit=kmh&timezone=Asia%2FAlmaty")
        data = await asyncio.to_thread(lambda: requests.get(url, timeout=10).json())
        d = data["current"]
        code = d["weather_code"]
        desc = WEATHER_CODES.get(code, "Неизвестно")
        icon = WEATHER_ICONS.get(code, "🌤")
        temp = d["temperature_2m"]
        feels = d["apparent_temperature"]
        humidity = d["relative_humidity_2m"]
        wind = d["wind_speed_10m"]
        return f"{icon} {desc}, {temp}°C (ощущается {feels}°C), влажность {humidity}%, ветер {wind} км/ч"
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return None


def determine_tool(text: str) -> str | None:
    if has_weather_intent(text):
        return "weather"
    if has_time_intent(text):
        return "time"
    search_keywords = [
        "найди", "поиск", "информация", "расскажи про", "что такое", "кто такой",
        "сколько стоит", "цена", "адрес", "контакты", "телефон", "расписание",
        "как добраться", "как пройти", "отель", "ресторан",
    ]
    if any(kw in text.lower() for kw in search_keywords):
        return "web_search"
    search_patterns = [
        r"\bгде\s+(купить|найти|можно|достать|заказать|взять|находится|расположен)\b",
    ]
    for p in search_patterns:
        if re.search(p, text.lower()):
            return "web_search"
    return None
