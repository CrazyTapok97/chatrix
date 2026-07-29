#!/usr/bin/env python3
"""
Chatrix-бот — Telegram бот с генерацией контента через OpenRouter API
Запуск: python chatrix.py
"""

import logging
import asyncio, time, json, os
import re
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.types import Message, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from handlers.generate import router as gen_router
from handlers.settings import router as settings_router
from handlers.misc import router as misc_router
from handlers.inline import router as inline_router
from handlers.mafia import router as mafia_router
from handlers.business import router as business_router
from handlers.native_features import router as native_router
from utils.ai_updater import update_models_cache
from utils.antispam import is_ratelimited

from utils.backups import backup_scheduler

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DebugMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            content = event.text or event.caption or ""
            logger.debug(f">>> RAW INPUT: '{content}' from Chat:{event.chat.id} Type:{event.chat.type}")
            user_id = event.from_user.id if event.from_user else 0
            if user_id:
                is_admin = user_id in ADMIN_IDS
                is_cmd = content.startswith("/")
                if is_cmd and is_ratelimited(event.chat.id, user_id, is_admin=is_admin, is_command=True):
                    logger.info(f"[ANTISPAM] Command from {user_id} rate-limited")
                    return
        return await handler(event, data)


async def heartbeat_loop(bot: Bot):
    path = "data/heartbeat.json"
    os.makedirs("data", exist_ok=True)
    fail_count = 0
    while True:
        try:
            # 1. Запись локального хертбита
            with open(path, "w") as f:
                json.dump({"timestamp": time.time(), "bot": "chatrix"}, f)
            
            # 2. Проверка связи с Telegram (Watchdog)
            await bot.get_me()
            fail_count = 0 # Сбрасываем счетчик при успехе
            
        except Exception as e:
            fail_count += 1
            logger.error(f"[WATCHDOG] Connection issue ({fail_count}/10): {e}")
            if fail_count >= 10:
                logger.critical("[WATCHDOG] Connection lost for 10 minutes. Self-terminating for restart...")
                exit(1) # Выход для перезапуска через systemd
                
        await asyncio.sleep(60)

async def models_update_loop():
    """Периодическое обновление списка моделей (раз в 24 часа)."""
    while True:
        try:
            logger.info("[MODELS] Running scheduled models update...")
            await update_models_cache()
        except Exception as e:
            logger.error(f"[MODELS] Error in update loop: {e}")
        await asyncio.sleep(24 * 3600) # 24 часа

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация middleware
    dp.message.outer_middleware(DebugMiddleware())

    # Регистрация роутеров (ПОРЯДОК ВАЖЕН!)
    dp.include_router(settings_router)
    dp.include_router(native_router)
    dp.include_router(gen_router)
    dp.include_router(inline_router)
    dp.include_router(mafia_router)
    dp.include_router(business_router)
    dp.include_router(misc_router)
    

    @dp.error()
    async def error_handler(event: ErrorEvent):
        logger.error(f"Error handling update: {event.exception}", exc_info=event.exception)

    # Регистрация команд в меню Telegram
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="HELP"),
        BotCommand(command="mafia", description="Начать игру в Мафию"),
        BotCommand(command="join", description="Войти в игру"),
        BotCommand(command="ready", description="Я готов к игре"),
        BotCommand(command="startmafia", description="Запустить игру"),
        BotCommand(command="settings", description="Настройки игры"),
    ])

    asyncio.create_task(heartbeat_loop(bot))
    asyncio.create_task(models_update_loop())
    asyncio.create_task(backup_scheduler(bot))
    
    # Первичный апдейт при старте
    await update_models_cache()

    logger.info("=== BOT READY ===")
    await dp.start_polling(bot, allowed_updates=[
        "message", "callback_query", "inline_query", "chosen_inline_result",
        "business_connection", "business_message", 
        "edited_business_message", "deleted_business_messages"
    ])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.exception(f"Bot crashed with exception: {e}")
        # Выходим с ошибкой, чтобы systemd перезапустил процесс
        exit(1)
