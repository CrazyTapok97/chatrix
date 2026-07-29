"""
Утилиты для отслеживания состояния бизнес-аккаунтов.
Помогают избежать ситуации, когда и бот, и владелец отвечают одновременно.
Данные сохраняются в файл для выживания при перезагрузках.
"""

import time
import json
import os
import logging

logger = logging.getLogger(__name__)

DATA_FILE = "data/business_connections.json"

# Хранилище: connection_id -> owner_id
_connections = {}

# Хранилище: (owner_id, chat_id) -> last_activity_timestamp
_last_activity = {}

def _load_connections():
    global _connections
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                _connections = json.load(f)
                logger.info(f"Загружено {_connections} бизнес-подключений из файла.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке бизнес-подключений: {e}")

def _save_connections():
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(_connections, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка при сохранении бизнес-подключений: {e}")

# Инициализация при импорте
_load_connections()

def register_connection(connection_id: str, owner_id: int):
    """Регистрирует связь ID подключения и ID владельца."""
    _connections[connection_id] = owner_id
    _save_connections()

def get_owner_id(connection_id: str) -> int:
    """Возвращает ID владельца для данного подключения."""
    # Приводим к строке, так как JSON ключи всегда строки
    return _connections.get(str(connection_id))

def update_activity(owner_id: int, chat_id: int):
    """Обновляет время последней активности владельца в конкретном чате."""
    _last_activity[(owner_id, chat_id)] = time.time()

def is_owner_active(owner_id: int, chat_id: int, threshold_seconds: int = 30) -> bool:
    """Проверяет, был ли владелец активен в чате за последние N секунд."""
    last_time = _last_activity.get((owner_id, chat_id), 0)
    return (time.time() - last_time) < threshold_seconds
