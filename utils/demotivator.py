"""
Генерация демотиватора с помощью Pillow.
Фото обрезается до квадрата, текст уменьшается чтобы влезть в одну строку.
"""
from __future__ import annotations
import io
from PIL import Image, ImageDraw, ImageFont

MAX_TITLE_WORDS = 6
MAX_SUB_WORDS   = 8

def _truncate(text: str, max_words: int) -> str:
    """Обрезает текст до max_words слов."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"

def _load_font(size: int):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()

def _fit_font(text: str, max_width: int, max_size: int, min_size: int, draw: ImageDraw.ImageDraw):
    """Уменьшает шрифт пока текст не влезет в max_width."""
    for size in range(max_size, min_size - 1, -1):
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return _load_font(min_size)

def _crop_to_square(img: Image.Image, size: int = 500) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top  = (h - side) // 2
    img  = img.crop((left, top, left + side, top + side))
    return img.resize((size, size), Image.LANCZOS)

def make_demotivator(photo_bytes: bytes, title: str, subtitle: str) -> bytes:
    # Переводим заголовок в верхний регистр
    title    = title.upper()

    img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    img = _crop_to_square(img, size=700)

    photo_size = 700
    border     = 2
    padding    = 20
    gap        = 8
    bottom_h   = 90

    canvas_w = photo_size + (padding + border + gap) * 2
    canvas_h = photo_size + (padding + border + gap) * 2 + bottom_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), "black")
    draw   = ImageDraw.Draw(canvas)

    rx0 = padding
    ry0 = padding
    rx1 = canvas_w - padding
    ry1 = padding + border + gap + photo_size + gap + border

    draw.rectangle([rx0, ry0, rx1, ry1], outline="white", width=border)
    canvas.paste(img, (padding + border + gap, padding + border + gap))

    max_text_w = canvas_w - padding * 2 - 10

    font_title = _fit_font(title,    max_text_w, max_size=30, min_size=12, draw=draw)
    font_sub   = _fit_font(subtitle, max_text_w, max_size=20, min_size=10, draw=draw)

    text_y = ry1 + 12

    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw   = bbox[2] - bbox[0]
    draw.text(((canvas_w - tw) // 2, text_y), title, fill="white", font=font_title)

    text_y += (bbox[3] - bbox[1]) + 8

    bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
    tw2   = bbox2[2] - bbox2[0]
    draw.text(((canvas_w - tw2) // 2, text_y), subtitle, fill="#cccccc", font=font_sub)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()