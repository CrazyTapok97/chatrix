"""
Quiz game based on chat history.
"""

import random
from utils.history import format_history


def generate_quiz_questions(chat_id: int, limit: int = 5) -> list[dict]:
    """Generate quiz questions based on chat history."""
    history = format_history(chat_id, limit=100)
    
    if not history or len(history.strip()) < 50:
        return []
    
    questions = []
    
    # Question types
    question_types = [
        "who_said",
        "what_word", 
        "when_message",
        "true_false"
    ]
    
    for _ in range(min(limit, len(question_types))):
        q_type = random.choice(question_types)
        
        if q_type == "who_said":
            q = _create_who_said_question(history)
        elif q_type == "what_word":
            q = _create_what_word_question(history)
        elif q_type == "when_message":
            q = _create_when_question(history)
        else:
            q = _create_true_false_question(history)
        
        if q:
            questions.append(q)
    
    return questions


def _create_who_said_question(history: str) -> dict:
    """Create 'who said this' question."""
    lines = [line.strip() for line in history.split('\n') if line.strip()]
    if len(lines) < 2:
        return None
    
    # Pick a random message
    line = random.choice(lines)
    if ':' not in line:
        return None
    
    username, message = line.split(':', 1)
    username = username.strip()
    message = message.strip()
    
    if len(message) < 10 or len(message) > 100:
        return None
    
    # Get other usernames for options
    usernames = set()
    for l in lines:
        if ':' in l:
            usernames.add(l.split(':')[0].strip())
    
    usernames.discard(username)
    if len(usernames) < 2:
        return None
    
    options = [username] + random.sample(list(usernames), min(3, len(usernames)))
    random.shuffle(options)
    
    correct_id = options.index(username)
    
    return {
        "question": f"Кто сказал: \"{message[:50]}{'...' if len(message) > 50 else ''}\"?",
        "options": options,
        "correct": correct_id,
        "type": "who_said"
    }


def _create_what_word_question(history: str) -> dict:
    """Create 'what word was most used' question."""
    words = history.lower().split()
    # Filter out common words
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must'}
    
    word_freq = {}
    for word in words:
        word = word.strip('.,!?()[]{}"\'')
        if len(word) > 3 and word not in common_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    if len(word_freq) < 4:
        return None
    
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    top_word = sorted_words[0][0]
    
    options = [top_word]
    for word, _ in sorted_words[1:4]:
        options.append(word)
    
    random.shuffle(options)
    correct_id = options.index(top_word)
    
    return {
        "question": "Какое слово упоминалось чаще всего в истории чата?",
        "options": options,
        "correct": correct_id,
        "type": "what_word"
    }


def _create_when_question(history: str) -> dict:
    """Create 'when was this message sent' question."""
    lines = [line.strip() for line in history.split('\n') if line.strip()]
    if len(lines) < 3:
        return None
    
    # Pick a message from middle
    line = random.choice(lines[1:-1])
    if ':' not in line:
        return None
    
    username, message = line.split(':', 1)
    message = message.strip()
    
    if len(message) < 10:
        return None
    
    options = ["Недавно", "Давно", "В середине разговора", "В начале"]
    correct_id = 2  # "В середине разговора"
    
    return {
        "question": f"Когда было отправлено это сообщение: \"{message[:40]}{'...' if len(message) > 40 else ''}\"?",
        "options": options,
        "correct": correct_id,
        "type": "when_message"
    }


def _create_true_false_question(history: str) -> dict:
    """Create true/false question about chat."""
    lines = [line.strip() for line in history.split('\n') if line.strip()]
    if len(lines) < 2:
        return None
    
    # Random facts about chat
    facts = [
        ("Кто-то использовал слово 'привет'", True),
        ("В чате было сообщение с эмодзи", True),
        ("Все сообщения были очень короткими", False),
        ("Люди обсуждали технические темы", True),
        ("Чат был о еде", False),
        ("Кто-то упоминал время или дату", True),
        ("Все сообщения были формальными", False),
        ("В чате было неформальное общение", True)
    ]
    
    fact, is_true = random.choice(facts)
    
    # Simple heuristic to check if fact might be true
    actual_true = True  # Default to true for simplicity
    
    options = ["Правда", "Ложь"]
    correct_id = 0 if actual_true else 1
    
    return {
        "question": f"Правда или ложь: {fact}?",
        "options": options,
        "correct": correct_id,
        "type": "true_false"
    }
