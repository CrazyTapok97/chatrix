import json
import os
import re
import tempfile
import time
from pathlib import Path

AI_CONFIG_FILE = Path("data/ai_config.json")
AI_METRICS_FILE = Path("data/ai_performance.json")
SYSTEM_PROMPTS_FILE = Path("data/system_prompts.json")
SLOT_ORDER = ("primary", "fallback", "fallback2", "fallback3", "fallback4", "final", "extra", "extra2", "extra3")
NON_TEXT_MARKERS = ("safety", "guard", "moderation", "content-safety", "lyria", "tts", "music", "audio")


def load_ai_config() -> dict:
    try:
        data = json.loads(AI_CONFIG_FILE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_system_prompts() -> dict:
    try:
        data = json.loads(SYSTEM_PROMPTS_FILE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_model_chain(config: dict | None = None) -> list[tuple[str, str]]:
    config = config or load_ai_config()
    chain = []
    seen = set()
    for slot in SLOT_ORDER:
        model = str(config.get(f"{slot}_model", "") or "").strip()
        provider = str(config.get(f"{slot}_provider", "groq") or "groq").strip().lower()
        if not model or any(marker in model.lower() for marker in NON_TEXT_MARKERS):
            continue
        key = (provider, model)
        if key not in seen:
            seen.add(key)
            chain.append(key)
    return chain


def detect_provider(model: str, cache: dict | None = None) -> str:
    model_lower = model.lower()
    cache = cache or {}
    if model in cache.get("groq", []):
        return "groq"
    if model in cache.get("openrouter", []):
        return "openrouter"
    if model_lower.startswith("gemini-") or model_lower.startswith("gemma-"):
        return "google"
    return "openrouter"


def save_ai_config(config: dict) -> None:
    AI_CONFIG_FILE.parent.mkdir(exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".ai_config_", dir=AI_CONFIG_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, AI_CONFIG_FILE)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def clean_model_response(content: str) -> str:
    text = (content or "").strip()
    # Remove <think> and <thinking>...</thinking> tags (reasoning models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    # If response starts with unclosed think tag, drop it
    if re.match(r"^<think>(?!.*</think>)", text, flags=re.IGNORECASE | re.DOTALL):
        return ""
    if re.match(r"^\)", text, flags=re.DOTALL):
        return ""
    if re.match(r"^<thinking>(?!.*</thinking>)", text, flags=re.IGNORECASE | re.DOTALL):
        return ""
    # Remove [/assistant] tag that some models (e.g. Qwen) append
    text = re.sub(r"\[/assistant\]", "", text, flags=re.IGNORECASE).strip()
    return text


def record_ai_result(model: str, success: bool, elapsed_ms: float | None = None, fallback: bool = False) -> None:
    try:
        data = json.loads(AI_METRICS_FILE.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data.setdefault("response_times", [])
    data.setdefault("errors", 0)
    data.setdefault("timeouts", 0)
    data.setdefault("fallback_count", 0)
    data.setdefault("total_requests", 0)
    data.setdefault("successful_requests", 0)
    data.setdefault("provider_stats", {})
    data["total_requests"] += 1
    data["last_updated"] = time.time()
    if success:
        data["successful_requests"] += 1
    else:
        data["errors"] += 1
    if fallback:
        data["fallback_count"] += 1
    if elapsed_ms is not None:
        data["response_times"].append(elapsed_ms)
        data["response_times"] = data["response_times"][-500:]
    stats = data["provider_stats"].setdefault(model, {"calls": 0, "success": 0, "errors": 0, "avg_time": 0})
    stats["calls"] += 1
    stats["success" if success else "errors"] += 1
    if elapsed_ms is not None:
        stats["avg_time"] = ((stats["avg_time"] * (stats["calls"] - 1)) + elapsed_ms) / stats["calls"]
    AI_METRICS_FILE.parent.mkdir(exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".ai_metrics_", dir=AI_METRICS_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, AI_METRICS_FILE)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise