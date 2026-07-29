import io
import textwrap
from PIL import Image, ImageDraw, ImageFont
import os

def _load_font(size: int):
    # Поиск шрифта, похожего на Impact
    paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Часто есть на Linux
        "C:\\Windows\\Fonts\\impact.ttf", # Windows
        "C:\\Windows\\Fonts\\arialbd.ttf", # Windows fallback
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()

def create_classic_meme(image_path: str, text: str) -> bytes:
    """
    Создает классический мем: текст сверху, белый цвет, черная обводка.
    """
    text = text.upper()
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Настройка шрифта и переноса текста
    # Подбираем размер шрифта в зависимости от ширины картинки
    font_size = int(width / 10)
    if font_size < 20: font_size = 20
    
    font = _load_font(font_size)
    
    # Перенос текста
    # Примерно определяем сколько символов влезет в строку
    avg_char_width = draw.textbbox((0, 0), "W", font=font)[2]
    chars_per_line = max(1, int(width * 0.9 / avg_char_width))
    lines = textwrap.wrap(text, width=chars_per_line)
    
    # Рисование текста
    y_offset = int(height * 0.05)
    line_spacing = int(font_size * 0.1)
    
    outline_width = max(1, int(font_size / 15))

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        
        x = (width - line_w) // 2
        
        # Рисуем обводку
        for adj_x in range(-outline_width, outline_width + 1):
            for adj_y in range(-outline_width, outline_width + 1):
                draw.text((x + adj_x, y_offset + adj_y), line, font=font, fill="black")
        
        # Рисуем основной текст
        draw.text((x, y_offset), line, font=font, fill="white")
        
        y_offset += line_h + line_spacing

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
