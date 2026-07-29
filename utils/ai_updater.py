import aiohttp
import logging
import json
import os
import tempfile
from config import OPENROUTER_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

MODELS_CACHE_FILE = "data/ai_models_cache.json"
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15)  # без таймаута запрос мог зависнуть бесконечно


def _load_existing_cache() -> dict:
    """Текущий кэш с диска — используется как fallback, если свежий запрос не удался."""
    if not os.path.exists(MODELS_CACHE_FILE):
        return {"openrouter": [], "groq": []}
    try:
        with open(MODELS_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {"openrouter": [], "groq": []}
    except Exception:
        return {"openrouter": [], "groq": []}


def _save_cache_atomic(models: dict) -> None:
    """Атомарная запись: через временный файл + os.replace, чтобы не повредить
    кэш при падении процесса посреди записи."""
    os.makedirs("data", exist_ok=True)
    dir_name = os.path.dirname(MODELS_CACHE_FILE) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(models, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, MODELS_CACHE_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


async def update_models_cache():
    """Скачивает список бесплатных моделей из OpenRouter и доступных из Groq.
    Если один из запросов не удался — для этого провайдера сохраняется
    предыдущее значение из кэша, а не пустой список (раньше неудачный запрос
    к OpenRouter полностью обнулял список моделей на следующие 24 часа,
    пока кэш не обновится снова)."""
    existing = _load_existing_cache()
    models = {
        "openrouter": list(existing.get("openrouter", [])),
        "groq": list(existing.get("groq", [])),
    }

    # 1. OpenRouter Free Models
    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            async with session.get("https://openrouter.ai/api/v1/models") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fresh = []
                    for m in data.get("data", []):
                        pricing = m.get("pricing", {})
                        # Проверяем, что модель бесплатная
                        if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
                            fresh.append(m["id"])
                    if fresh:
                        models["openrouter"] = fresh
                        logger.info(f"Updated OpenRouter free models: {len(fresh)} found")
                    else:
                        logger.warning("OpenRouter returned 0 free models — keeping previous cache")
                else:
                    logger.error(f"Failed to fetch OpenRouter models: {resp.status} — keeping previous cache")
    except Exception as e:
        logger.error(f"Error updating OpenRouter models: {e} — keeping previous cache")

    # 2. Groq Models
    if GROQ_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
                async with session.get("https://api.groq.com/openai/v1/models", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        fresh = [m["id"] for m in data.get("data", [])]
                        if fresh:
                            models["groq"] = fresh
                            logger.info(f"Updated Groq models: {len(fresh)} found")
                        else:
                            logger.warning("Groq returned 0 models — keeping previous cache")
                    else:
                        logger.error(f"Failed to fetch Groq models: {resp.status} — keeping previous cache")
        except Exception as e:
            logger.error(f"Error updating Groq models: {e} — keeping previous cache")

    # Сохраняем в кэш (атомарно)
    try:
        _save_cache_atomic(models)
    except Exception as e:
        logger.error(f"Failed to save models cache: {e}")

    return models

def get_cached_models():
    """Возвращает список моделей из кэша."""
    if not os.path.exists(MODELS_CACHE_FILE):
        return None
    try:
        with open(MODELS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None