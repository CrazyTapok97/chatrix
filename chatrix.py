#!/usr/bin/env python3
"""
Telegram бот с генерацией контента через Claude API
Запуск: python bot.py
"""

import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers.generate import router as gen_router
from handlers.settings import router as settings_router
from handlers.misc import router as misc_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(settings_router)
    dp.include_router(gen_router)
    dp.include_router(misc_router)

    logger.info("Сглыпа запущен!")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
