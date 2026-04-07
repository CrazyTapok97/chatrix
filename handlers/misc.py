"""
Прочие хэндлеры: /start, S h, сбор истории сообщений и фото
"""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from utils.history import add_message, add_photo
from utils.likes import top
from utils.user_stats import user_stats
from utils.quiz import generate_quiz_questions
from utils.challenges import create_challenge, get_active_challenge, join_challenge, vote_for_demotivator

router = Router()

HELP_TEXT = """
🤖 <b>Chatrix</b> — генератор контента

<b>Команды:</b>

<code>S g</code> — панель генерации контента
<code>S g &lt;начало&gt;</code> — текст с заданным началом
<code>S g &lt;число 1-250&gt;</code> — текст заданной длины
<code>S g l</code> — длинный текст
<code>S g w</code> — случайное слово из чата
<code>S g w &lt;число 1-50&gt;</code> — слово заданной длины
<code>S g p</code> — опрос на основе переписки
<code>S g q</code> — викторина на основе переписки
<code>S g m</code> — мем на основе переписки
<code>S g d</code> — демотиватор (реплай на фото или случайное фото из чата)
<code>S g a</code> — анекдот на основе переписки
<code>S g r</code> — случайная фраза из чата
<code>S top</code> — лучшие демотиваторы чата
<code>S stats</code> — ваша статистика лайков
<code>S game quiz</code> — викторина о чате
<code>S challenge create &lt;theme&gt;</code> — создать челлендж
<code>S challenge</code> — активный челлендж
<code>S c</code> — настройки (только для администраторов)
<code>S h</code> — помощь
""".strip()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply(
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n{HELP_TEXT}",
        parse_mode="HTML",
    )


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Hh]$"))
async def cmd_help(message: Message):
    await message.reply(HELP_TEXT, parse_mode="HTML")


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Tt][Oo][Pp]$"))
async def cmd_top(message: Message):
    """Shows top demotivators with likes."""
    top_list = top(message.chat.id, limit=5)
    if not top_list:
        await message.reply("Пока нет демотиваторов с лайками! Будьте первым!")
        return
    
    text = "🏆 Топ демотиваторов чата:\n\n"
    for i, item in enumerate(top_list, 1):
        text += f"{i}. {item['title']}\n"
        text += f"   {item['subtitle']}\n"
        text += f"   Рейтинг: {item['likes']} - {item['dislikes']} = {item['score']}\n\n"
    
    await message.reply(text, parse_mode="HTML")


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Ss][Tt][Aa][Tt][Ss]$"))
async def cmd_stats(message: Message):
    """Shows user statistics for likes."""
    stats = user_stats(message.chat.id, message.from_user.id)
    
    if stats["total_votes"] == 0:
        await message.reply("Вы еще не голосовали за демотиваторы! Начните оценивать работы других.")
        return
    
    text = f"📊 Ваша статистика:\n\n"
    text += f"Всего голосов: {stats['total_votes']}\n"
    text += f"Лайков поставлено: {stats['likes_given']}\n"
    text += f"Дизлайков поставлено: {stats['dislikes_given']}\n"
    
    if stats["top_voted"]:
        text += f"\n🏆 Ваши лучшие оценки:\n"
        for i, item in enumerate(stats["top_voted"], 1):
            text += f"{i}. {item['title']}\n"
            text += f"   {item['subtitle']} (рейтинг: +{item['score']})\n"
    
    await message.reply(text, parse_mode="HTML")


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Gg][Aa][Mm][Ee]\s+[Qq][Uu][Ii][Zz]$"))
async def cmd_game_quiz(message: Message):
    """Generate quiz about chat history."""
    questions = generate_quiz_questions(message.chat.id, limit=3)
    
    if not questions:
        await message.reply("Недостаточно истории чата для викторины! Напишите больше сообщений.")
        return
    
    await message.reply("🎮 Викторина о вашем чате:\n")
    
    for i, q in enumerate(questions, 1):
        text = f"Вопрос {i}: {q['question']}\n\n"
        for j, option in enumerate(q['options']):
            text += f"{j+1}. {option}\n"
        
        text += f"\nОтвет: {q['options'][q['correct']]} ({q['type']})"
        
        await message.reply(text, parse_mode="HTML")


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Cc][Hh][Aa][Ll][Ll][Ee][Nn][Gg][Ee]\s+[Cc][Rr][Ee][Aa][Tt][Ee]\s+(.+)$"))
async def cmd_challenge_create(message: Message):
    """Create new challenge."""
    import re
    m = re.match(r"(?i)^[Ss]\s+[Cc][Hh][Aa][Ll][Ll][Ee][Nn][Gg][Ee]\s+[Cc][Rr][Ee][Aa][Tt][Ee]\s+(.+)$", message.text)
    theme = m.group(1).strip()
    
    challenge = await create_challenge(
        chat_id=message.chat.id,
        creator_id=message.from_user.id,
        theme=theme,
        duration_hours=24
    )
    
    text = f"🏁 Челлендж создан!\n\n"
    text += f"Тема: {theme}\n"
    text += f"Длительность: 24 часа\n"
    text += f"ID челленджа: {challenge['id']}\n\n"
    text += f"Чтобы участвовать: создайте демотиватор и напишите 'S challenge join {challenge['id']}'"
    
    await message.reply(text, parse_mode="HTML")


@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Cc][Hh][Aa][Ll][Ll][Ee][Nn][Gg][Ee]$"))
async def cmd_challenge_info(message: Message):
    """Show active challenge info."""
    challenge = await get_active_challenge(message.chat.id)
    
    if not challenge:
        await message.reply("Нет активных челленджей! Создайте новый: 'S challenge create <тема>'")
        return
    
    text = f"🏁 Активный челлендж:\n\n"
    text += f"Тема: {challenge['theme']}\n"
    text += f"Участников: {len(challenge['participants'])}\n"
    text += f"Заканчивается: {challenge['expires_at'][:16]}\n"
    
    if challenge["participants"]:
        text += f"\nУчастники:\n"
        for user_id, demot in challenge["participants"].items():
            text += f"- Пользователь {user_id}: {demot['title']}\n"
    
    await message.reply(text, parse_mode="HTML")


@router.message(F.photo)
async def collect_photo(message: Message):
    """Сохраняет file_id фото из чата."""
    file_id = message.photo[-1].file_id
    await add_photo(message.chat.id, file_id)
    # Если к фото есть подпись — сохраняем и её
    if message.caption:
        username = message.from_user.username or message.from_user.first_name or "?"
        await add_message(message.chat.id, username, message.caption)


@router.message(F.text)
async def collect_message(message: Message):
    """Собирает все текстовые сообщения в историю чата."""
    if not message.text:
        return
    if message.text[:2].upper() == "S " or message.text.startswith("/"):
        return
    username = message.from_user.username or message.from_user.first_name or "?"
    await add_message(message.chat.id, username, message.text)