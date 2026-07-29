"""
Генерация демотиватора с помощью Pillow.
Фото сжимается до квадрата 1:1 без обрезки, текст уменьшается чтобы влезть в одну строку.
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

def _resize_to_square(img: Image.Image, size: int = 500) -> Image.Image:
    """
    Сжимает изображение до формата 1:1 без обрезки.
    Всё изображение сохраняется, пропорции меняются до квадрата.
    """
    return img.resize((size, size), Image.LANCZOS)

def _crop_to_square_sticker(img: Image.Image, size: int = 512) -> Image.Image:
    """
    Умная обрезка изображения до формата 1:1 для стикеров.
    Использует стандартный размер 512x512 для Telegram стикеров.
    """
    w, h = img.size
    
    # Определяем размер квадрата - берем меньшую сторону
    side = min(w, h)
    
    # Центрируем обрезку для сохранения главного объекта
    left = (w - side) // 2
    top = (h - side) // 2
    
    # Обрезаем до квадрата
    img = img.crop((left, top, left + side, top + side))
    
    # Изменяем размер до стандартного размера стикера
    return img.resize((size, size), Image.LANCZOS)

def make_sticker(photo_bytes: bytes) -> bytes:
    """
    Создает стикер из изображения с обрезкой в формат 1:1.
    Использует стандартный размер 512x512 для Telegram стикеров.
    """
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    img = _crop_to_square_sticker(img, size=512)
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def make_demotivator(photo_bytes: bytes, title: str, subtitle: str) -> bytes:
    # Переводим заголовок в верхний регистр
    title    = title.upper()

    img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    img = _resize_to_square(img, size=500)

    photo_size = 500
    border     = 2
    padding    = 40
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


def make_gif_demotivator(photo_bytes: bytes, title: str, subtitle: str) -> bytes:
    """Создает анимированный демотиватор из GIF с оптимизацией скорости."""
    title = title.upper()
    gif_in = Image.open(io.BytesIO(photo_bytes))
    
    # Увеличиваем размер для лучшего качества
    photo_size = 600 

    frames = []
    durations = []

    border     = 2
    padding    = 40
    gap        = 8
    bottom_h   = 90
    canvas_w = photo_size + (padding + border + gap) * 2
    canvas_h = photo_size + (padding + border + gap) * 2 + bottom_h

    temp_canvas = Image.new("RGB", (canvas_w, canvas_h), "black")
    draw = ImageDraw.Draw(temp_canvas)

    rx0, ry0 = padding, padding
    rx1 = canvas_w - padding
    ry1 = padding + border + gap + photo_size + gap + border

    max_text_w = canvas_w - padding * 2 - 10
    font_title = _fit_font(title, max_text_w, 32, 12, draw)
    font_sub = _fit_font(subtitle, max_text_w, 20, 10, draw)

    text_y = ry1 + 12
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((canvas_w - tw) // 2, text_y), title, fill="white", font=font_title)
    text_y += (bbox[3] - bbox[1]) + 8
    bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((canvas_w - tw2) // 2, text_y), subtitle, fill="#cccccc", font=font_sub)
    
    total_frames = getattr(gif_in, "n_frames", 1)
    # Оптимизация: если кадров слишком много, пропускаем часть
    step = 1
    if total_frames > 30: step = 2
    if total_frames > 60: step = 3
    
    for frame_idx in range(0, total_frames, step):
        gif_in.seek(frame_idx)
        frame = gif_in.convert("RGB")
        frame = frame.resize((photo_size, photo_size), Image.NEAREST) # NEAREST быстрее LANCZOS
        
        canvas = temp_canvas.copy()
        canvas.paste(frame, (padding + border + gap, padding + border + gap))
        
        draw_frame = ImageDraw.Draw(canvas)
        draw_frame.rectangle([rx0, ry0, rx1, ry1], outline="white", width=border)
        
        frames.append(canvas)
        # Умножаем длительность на шаг, чтобы скорость осталась прежней
        durations.append(gif_in.info.get('duration', 100) * step)
    
    buf = io.BytesIO()
    if frames:
        frames[0].save(
            buf, format="GIF", save_all=True, append_images=frames[1:],
            duration=durations, loop=0, optimize=True
        )
    return buf.getvalue()


def make_video_demotivator(video_path: str, title: str, subtitle: str) -> str:
    """
    Создает анимированный MP4 демотиватор из видео с помощью moviepy.
    Возвращает путь к временному файлу.
    """
    try:
        from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    except ImportError:
        # Для старых версий moviepy
        from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    
    import numpy as np
    import os
    
    title = title.upper()
    clip = VideoFileClip(video_path)
    
    # Ограничиваем длительность 5 секундами для скорости
    # В MoviePy 2.x subclip -> subclipped
    if clip.duration > 5:
        if hasattr(clip, "subclipped"):
            clip = clip.subclipped(0, 5)
        else:
            clip = clip.subclip(0, 5)
        
    # Параметры (уменьшены для скорости)
    # Увеличенные параметры
    photo_size = 600
    border     = 2
    padding    = 40
    gap        = 8
    bottom_h   = 90
    canvas_w = photo_size + (padding + border + gap) * 2
    canvas_h = photo_size + (padding + border + gap) * 2 + bottom_h

    # Создаем статичную подложку (черный фон + текст + рамка)
    bg = Image.new("RGB", (canvas_w, canvas_h), "black")
    draw = ImageDraw.Draw(bg)
    rx0, ry0 = padding, padding
    rx1 = canvas_w - padding
    ry1 = padding + border + gap + photo_size + gap + border

    max_text_w = canvas_w - padding * 2 - 10
    font_title = _fit_font(title, max_text_w, 32, 12, draw)
    font_sub = _fit_font(subtitle, max_text_w, 20, 10, draw)

    text_y = ry1 + 12
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((canvas_w - tw) // 2, text_y), title, fill="white", font=font_title)
    text_y += (bbox[3] - bbox[1]) + 8
    bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((canvas_w - tw2) // 2, text_y), subtitle, fill="#cccccc", font=font_sub)
    draw.rectangle([rx0, ry0, rx1, ry1], outline="white", width=border)

    
    # Конвертируем PIL в массив для moviepy
    bg_array = np.array(bg)
    
    # В MoviePy 2.x методы изменились: set_duration -> with_duration, set_position -> with_position
    if hasattr(ImageClip(bg_array), "with_duration"):
        bg_clip = ImageClip(bg_array).with_duration(clip.duration)
        video_pos = (padding + border + gap, padding + border + gap)
        # В 2.x resized принимает (width, height) напрямую без newsize
        clip_resized = clip.resized((photo_size, photo_size))
        final_video = CompositeVideoClip([bg_clip, clip_resized.with_position(video_pos)])
    else:
        # Для старых версий 1.x
        bg_clip = ImageClip(bg_array).set_duration(clip.duration)
        video_pos = (padding + border + gap, padding + border + gap)
        clip_resized = clip.resize(newsize=(photo_size, photo_size))
        final_video = CompositeVideoClip([bg_clip, clip_resized.set_position(video_pos)])
    
    out_path = video_path + "_demot.mp4"
    # Сохраняем с низким битрейтом и yuv420p для совместимости с Telegram Animation
    final_video.write_videofile(
        out_path, 
        codec="libx264", 
        audio=False, 
        fps=15, 
        logger=None, 
        bitrate="500k",
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    
    clip.close()
    final_video.close()
    
    return out_path
