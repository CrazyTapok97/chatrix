import ast
import asyncio
import json
import html
import math
import operator
import os
import random
import re
import tempfile
import urllib.parse
from collections import Counter
from pathlib import Path

import aiohttp

from utils.ai import _ask
from utils.ai_updater import get_cached_models
from utils.history import get_history

logger = __import__("logging").getLogger(__name__)

DATA_DIR = Path("data")
TASKS_FILE = DATA_DIR / "native_tasks.json"
DRAW_STYLE_PRESETS = {
    "--realistic": "photorealistic, natural colors, realistic lighting, detailed textures",
    "--photo": "photorealistic, natural colors, realistic lighting, detailed textures",
    "--cinema": "cinematic still, dramatic lighting, film color grading",
    "--anime": "high quality anime illustration, clean line art, expressive lighting",
    "--art": "detailed digital painting, rich colors, polished concept art",
    "--poster": "poster design, strong composition, bold shapes",
}
DRAW_NEGATIVE = "blurry, low quality, deformed, duplicate, watermark, text, logo"

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {"sqrt": math.sqrt, "abs": abs, "round": round, "sin": math.sin, "cos": math.cos}
_CONSTANTS = {"pi": math.pi, "e": math.e}


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Слишком большая степень")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        if node.keywords or len(node.args) > 2:
            raise ValueError("Недопустимый вызов")
        return _FUNCTIONS[node.func.id](*[_evaluate(arg) for arg in node.args])
    raise ValueError("Недопустимое выражение")


def safe_calculate(expression: str):
    if len(expression) > 200:
        raise ValueError("Выражение слишком длинное")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
        result = _evaluate(tree)
    except (SyntaxError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Не удалось вычислить выражение") from exc
    if isinstance(result, (int, float)) and (not math.isfinite(result) or abs(result) > 1e100):
        raise ValueError("Результат выходит за допустимые пределы")
    return result


def parse_draw_request(prompt: str) -> tuple[str, int, int, str]:
    text = prompt.strip()
    width, height = 1024, 1024
    styles = ["high quality, coherent composition, sharp focus"]
    for flag, size in {
        "--wide": (1344, 768), "--landscape": (1344, 768),
        "--portrait": (768, 1344), "--vertical": (768, 1344),
        "--square": (1024, 1024),
    }.items():
        if flag in text:
            width, height = size
            text = text.replace(flag, " ")
    for flag, style in DRAW_STYLE_PRESETS.items():
        if flag in text:
            styles.append(style)
            text = text.replace(flag, " ")
    return re.sub(r"\s+", " ", text).strip(), width, height, ", ".join(styles)


def parse_ship_pair(value: str) -> tuple[str, str]:
    for separator in (" и ", " + ", " & "):
        if separator in value:
            first, second = (part.strip() for part in value.split(separator, 1))
            if first and second:
                return first, second
    raise ValueError("Формат: /ship Маша и Вася")


async def ask_ai(prompt: str, max_tokens: int = 700, image_url: str | None = None, sys_prompt: str | None = None) -> str:
    result = await _ask(prompt, max_tokens=max_tokens, image_url=image_url, sys_prompt=sys_prompt)
    return (result or "ИИ не вернул ответ.").strip()


async def run_agent(request: str) -> str:
    plan = await ask_ai(
        "Разбей задачу на максимум три конкретных шага. Верни только нумерованный список.\nЗадача: " + request,
        350,
    )
    steps = []
    for line in plan.splitlines():
        cleaned = re.sub(r"^\s*(?:\d+[.)]|[-*])\s*", "", line).strip()
        if cleaned and cleaned != line.strip() or re.match(r"^\s*\d+[.)]", line):
            steps.append(cleaned)
    steps = [step for step in steps if step][:3] or [request]
    results = []
    for step in steps:
        results.append(await ask_ai(f"Выполни этот шаг задачи конкретно и без выдуманных ссылок:\n{step}", 550))
    joined = "\n\n".join(f"Шаг {index}: {result}" for index, result in enumerate(results, 1))
    return await ask_ai(f"Собери итоговый ответ на задачу: {request}\n\nРезультаты:\n{joined}", 900)


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {"User-Agent": "Mozilla/5.0 Chatrix/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.post("https://html.duckduckgo.com/html/", data={"q": query}) as response:
            body = await response.text()
            if response.status != 200:
                raise RuntimeError(f"Поиск вернул HTTP {response.status}")
    links = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.IGNORECASE | re.DOTALL
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', body, flags=re.IGNORECASE | re.DOTALL
    )
    results = []
    for index, (url, title) in enumerate(links[:max_results]):
        clean_title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        snippet = snippets[index] if index < len(snippets) else ""
        clean_snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet)).strip()
        results.append({"title": clean_title, "body": clean_snippet, "href": html.unescape(url)})
    return results

async def improve_draw_prompt(prompt: str, style: str, redraw: bool = False) -> str:
    instruction = (
        "Rewrite the image request as an improved, more detailed English text-to-image prompt. "
        "Make it more vivid and precise to better match the original intent. "
        if redraw else
        "Rewrite the image request as one detailed English text-to-image prompt. Preserve the exact main subject. "
    )
    return await ask_ai(
        instruction + "No explanations, markdown or quotes. " + f"Style: {style}\nRequest: {prompt}",
        300,
    )


async def generate_image(prompt: str, redraw: bool = False) -> bytes:
    clean, width, height, style = parse_draw_request(prompt)
    if not clean:
        raise ValueError("Добавь описание изображения")
    final_prompt = await improve_draw_prompt(clean, style, redraw=redraw)

    # Magic Hour API (основной)
    mh_key = os.getenv("MAGIC_HOUR_API_KEY", "").strip()
    if mh_key:
        try:
            return await _generate_image_magic_hour(final_prompt, width, height, style)
        except Exception as exc:
            logger.warning("Magic Hour failed, falling back to Pollinations: %s", exc)

    # Pollinations.ai (фолбэк)
    return await _generate_image_pollinations(final_prompt, width, height)


async def _generate_image_magic_hour(prompt: str, width: int, height: int, style_str: str) -> bytes:
    from magic_hour import Client as MHClient

    orientation = "square"
    if width > height:
        orientation = "landscape"
    elif height > width:
        orientation = "portrait"

    tool = "general"
    low_style = style_str.lower()
    if "anime" in low_style:
        tool = "ai-anime-generator"
    elif "realistic" in low_style or "photo" in low_style:
        tool = "ai-photo-generator"
    elif "art" in low_style:
        tool = "ai-art-generator"

    loop = asyncio.get_event_loop()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await loop.run_in_executor(
            None,
            lambda: MHClient(token=os.environ["MAGIC_HOUR_API_KEY"]).v1.ai_image_generator.generate(
                image_count=1,
                style={"prompt": prompt, "tool": tool},
                orientation=orientation,
                wait_for_completion=True,
                download_outputs=True,
                download_directory=tmpdir,
            ),
        )
        paths = getattr(result, "downloaded_paths", None)
        if not paths:
            raise RuntimeError("Magic Hour не вернул файл")
        path = paths[0] if isinstance(paths, list) else paths
        with open(path, "rb") as f:
            return f.read()


async def _generate_image_pollinations(prompt: str, width: int, height: int) -> bytes:
    encoded = urllib.parse.quote(prompt, safe="")
    query = urllib.parse.urlencode({
        "model": os.getenv("DRAW_MODEL", "flux"), "width": width, "height": height,
        "seed": random.randint(1, 2_000_000_000), "nologo": "true", "enhance": "true",
        "negative": DRAW_NEGATIVE,
    })
    timeout = aiohttp.ClientTimeout(total=100)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"https://image.pollinations.ai/prompt/{encoded}?{query}") as response:
            data = await response.read()
            if response.status != 200 or not response.headers.get("Content-Type", "").startswith("image/"):
                raise RuntimeError(f"Pollinations вернул HTTP {response.status}")
            return data


async def synthesize_speech(text: str) -> bytes:
    try:
        import edge_tts
    except ImportError:
        timeout = aiohttp.ClientTimeout(total=30)
        params = {"ie": "UTF-8", "client": "tw-ob", "tl": "ru", "q": text[:200]}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://translate.google.com/translate_tts", params=params) as response:
                audio = await response.read()
                if response.status != 200 or not audio:
                    raise RuntimeError(f"TTS вернул HTTP {response.status}")
                return audio
    voice = os.getenv("TTS_VOICE", "ru-RU-DmitryNeural")
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        await edge_tts.Communicate(text[:3000], voice).save(path)
        return await asyncio.to_thread(Path(path).read_bytes)
    finally:
        Path(path).unlink(missing_ok=True)


def _load_task_records() -> list[dict]:
    try:
        data = json.loads(TASKS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        data = []
    return data if isinstance(data, list) else []


def load_tasks(user_id: int) -> list[str]:
    return [
        str(item.get("text", ""))
        for item in _load_task_records()
        if int(item.get("sender_id", 0) or 0) == user_id and not item.get("completed") and item.get("text")
    ]


def add_task(user_id: int, task: str, chat_id: int = 0) -> list[str]:
    DATA_DIR.mkdir(exist_ok=True)
    records = _load_task_records()
    next_id = max((int(item.get("id", 0) or 0) for item in records), default=0) + 1
    records.append({
        "id": next_id,
        "text": task,
        "sender_id": user_id,
        "chat_id": chat_id,
        "completed": False,
        "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    })
    tmp = TASKS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TASKS_FILE)
    return load_tasks(user_id)

def model_report() -> str:
    cache = get_cached_models() or {"openrouter": [], "groq": []}
    groq = cache.get("groq", [])
    openrouter = cache.get("openrouter", [])
    from utils.ai_config import build_model_chain
    chain = build_model_chain()
    configured = " → ".join(f"{model} [{provider}]" for provider, model in chain) or "не настроена"
    lines = ["🤖 Доступные модели", "", f"Цепочка: {configured}", "", f"Groq ({len(groq)}):"]
    lines.extend(f"• {name}" for name in groq[:20])
    lines.extend(["", f"OpenRouter FREE ({len(openrouter)}):"])
    lines.extend(f"• {name}" for name in openrouter[:30])
    return "\n".join(lines)[:4000]


def chat_top(chat_id: int, limit: int = 10) -> list[tuple[str, int]]:
    counts = Counter(item.get("u", "Без имени") for item in get_history(chat_id) if item.get("u"))
    return counts.most_common(limit)