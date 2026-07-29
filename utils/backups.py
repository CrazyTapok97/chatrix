import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import zipfile
from datetime import datetime

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

BACKUP_DIR = "data/backups"
STATE_FILE = "data/backup_state.json"


def _load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"last_week": 0, "last_sent_month": 0}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def create_backup_path() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"chatrix_backup_{timestamp}.zip")
    return path


def create_backup() -> str | None:
    path = create_backup_path()
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            base = os.getcwd()
            for root, _, files in os.walk(base):
                rel = os.path.relpath(root, base)
                for f in files:
                    fpath = os.path.join(root, f)
                    if fpath.startswith(os.path.join(base, BACKUP_DIR)):
                        continue
                    if f.endswith(".pyc") or "__pycache__" in fpath:
                        continue
                    if f == ".env":
                        continue
                    zf.write(fpath, os.path.join(rel, f))
        size = os.path.getsize(path)
        logger.info(f"[BACKUP] Created: {path} ({size / 1024 / 1024:.1f} MB)")
        return path
    except Exception as e:
        logger.error(f"[BACKUP] Failed: {e}")
        return None


async def backup_scheduler(bot):
    await asyncio.sleep(60)
    logger.info("[BACKUP] Scheduler started")
    state = _load_state()

    while True:
        try:
            now = datetime.now()
            current_week = now.isocalendar()[1]
            current_month = now.month

            if now.weekday() == 6 and now.hour == 3 and current_week != state.get("last_week", 0):
                path = await asyncio.to_thread(create_backup)
                if path:
                    state["last_week"] = current_week
                    _save_state(state)
                    logger.info(f"[BACKUP] Weekly backup created")

            if current_month != state.get("last_sent_month", 0):
                if now.day > 1 or (now.day == 1 and now.hour >= 1):
                    path = await asyncio.to_thread(create_backup)
                    if path:
                        for admin_id in ADMIN_IDS:
                            try:
                                with open(path, "rb") as f:
                                    await bot.send_document(
                                        chat_id=admin_id,
                                        document=f,
                                        caption=f"📦 **Ежемесячный бэкап**\n📅 {now.strftime('%d.%m.%Y')}"
                                    )
                                logger.info(f"[BACKUP] Sent to admin {admin_id}")
                            except Exception as e:
                                logger.error(f"[BACKUP] Failed to send to {admin_id}: {e}")
                        state["last_sent_month"] = current_month
                        _save_state(state)
        except Exception as e:
            logger.error(f"[BACKUP] Scheduler error: {e}")
        await asyncio.sleep(60)
