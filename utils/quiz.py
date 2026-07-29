"""
True Random Game Engine.
No AI, no templates, just raw data shuffling.
"""

import random
from utils.history import get_history


def generate_quiz_questions(chat_id: int, limit: int = 5) -> list[dict]:
    """
    Создает абсолютно абстрактные викторины (Poll с правильным ответом).
    Вопрос — эмодзи, варианты — обрывки истории чата.
    """
    msgs = get_history(chat_id, limit=300)
    if len(msgs) < 10:
        return []

    questions = []
    emojis = ["🌟", "😁", "🥰", "🤬", "🧐", "🤯", "👄", "😊", "❤️", "🌚", "💎", "🔥", "🌈", "🍄", "🎲", "⚡️"]
    
    # Собираем всё подряд из истории
    raw_pool = []
    for m in msgs:
        t = m["t"].strip()
        if len(t) > 1:
            raw_pool.append(t)
    
    if len(raw_pool) < 5:
        return []

    for _ in range(limit):
        # Вопрос — случайные эмодзи
        q_len = random.randint(1, 4)
        question = " ".join(random.sample(emojis, q_len))
        
        # Выбираем от 3 до 5 вариантов из истории
        opt_count = random.randint(3, 5)
        options = random.sample(raw_pool, opt_count)
        
        # Обрезаем под лимит Telegram
        options = [opt[:100] for opt in options]
        
        # Случайный индекс правильного ответа
        correct_id = random.randint(0, opt_count - 1)
        
        questions.append({
            "question": f"[QUIZ] {question}",
            "options": options,
            "correct": correct_id
        })

    return questions
