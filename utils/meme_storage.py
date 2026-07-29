import sqlite3
import os
import logging
import random

logger = logging.getLogger(__name__)

DB_PATH = "data/memes.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            file_id TEXT,
            thumb_file_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

async def index_memes(memes_dir="memes"):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    valid_extensions = ('.jpg', '.jpeg', '.png')
    
    # Нормализуем пути, используя прямые слэши для консистентности в БД
    files = []
    for root, dirs, filenames in os.walk(memes_dir):
        for filename in filenames:
            if filename.lower().endswith(valid_extensions):
                # Создаем путь с прямыми слэшами
                file_path = os.path.join(root, filename).replace('\\', '/')
                files.append(file_path)
    
    new_indexed_count = 0
    for file_path in files:
        try:
            cursor.execute("INSERT OR IGNORE INTO memes (file_path) VALUES (?)", (file_path,))
            if cursor.rowcount > 0:
                new_indexed_count += 1
        except Exception as e:
            logger.error(f"Error indexing {file_path}: {e}")
            
    conn.commit()
    # Get total count after indexing
    cursor.execute("SELECT COUNT(*) FROM memes")
    total_count = cursor.fetchone()[0]
    conn.close()
    
    logger.info(f"Indexing complete. New records added: {new_indexed_count}. Total records in DB: {total_count}")
    return new_indexed_count, total_count

def get_memes(limit=50, offset=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path, file_id, thumb_file_id FROM memes LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_random_memes(limit=50, offset=0, seed=1):
    """Возвращает случайную подборку шаблонов для inline-галереи."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, file_path, file_id, thumb_file_id
        FROM memes
        WHERE file_id IS NOT NULL AND file_id != ''
        ORDER BY ((id * ?) % 2147483647), id
        LIMIT ? OFFSET ?
        """,
        (seed, limit, offset),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_random_meme():
    """Возвращает случайный существующий локальный шаблон."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, file_path, file_id, thumb_file_id FROM memes ORDER BY RANDOM() LIMIT 20"
    )
    rows = cursor.fetchall()
    conn.close()
    valid = [row for row in rows if os.path.isfile(row[1])]
    return random.choice(valid) if valid else None

def update_file_id(meme_id, file_id, thumb_file_id=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if thumb_file_id:
        cursor.execute("UPDATE memes SET file_id = ?, thumb_file_id = ? WHERE id = ?", (file_id, thumb_file_id, meme_id))
    else:
        cursor.execute("UPDATE memes SET file_id = ? WHERE id = ?", (file_id, meme_id))
    conn.commit()
    conn.close()

def add_meme(file_path, file_id=None, thumb_file_id=None):
    """Добавляет один шаблон и возвращает его постоянный ID."""
    init_db()
    normalized_path = file_path.replace('\\', '/')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO memes (file_path, file_id, thumb_file_id)
        VALUES (?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            file_id = COALESCE(excluded.file_id, memes.file_id),
            thumb_file_id = COALESCE(excluded.thumb_file_id, memes.thumb_file_id)
        """,
        (normalized_path, file_id, thumb_file_id),
    )
    conn.commit()
    cursor.execute("SELECT id FROM memes WHERE file_path = ?", (normalized_path,))
    meme_id = cursor.fetchone()[0]
    conn.close()
    return meme_id

def get_meme_by_id(meme_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path, file_id, thumb_file_id FROM memes WHERE id = ?", (meme_id,))
    row = cursor.fetchone()
    conn.close()
    return row
