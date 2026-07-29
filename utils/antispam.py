import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 3
BURST_LIMIT = 15
BURST_WINDOW = 60
IGNORE_DURATION = 60

_user_last_cmd = {}
_user_burst = defaultdict(list)
_user_ignored_until = {}
_ratelimited_msgs = set()


def _check_ratelimit(chat_id: int, user_id: int, is_admin: bool, is_command: bool) -> bool:
    now = time.time()
    key = (chat_id, user_id)

    if key in _user_ignored_until and now < _user_ignored_until[key]:
        remaining = int(_user_ignored_until[key] - now)
        logger.info(f"[ANTISPAM] Ignoring {user_id} in {chat_id} ({remaining}s remaining)")
        return False

    if is_admin:
        return True

    if is_command:
        last = _user_last_cmd.get(key, 0)
        if now - last < COOLDOWN_SECONDS:
            logger.info(f"[ANTISPAM] Cooldown for {user_id}: {int(COOLDOWN_SECONDS - (now - last))}s left")
            return False
        _user_last_cmd[key] = now

    history = _user_burst.get(key, [])
    history = [t for t in history if now - t < BURST_WINDOW]
    if len(history) >= BURST_LIMIT:
        _user_ignored_until[key] = now + IGNORE_DURATION
        logger.warning(f"[ANTISPAM] User {user_id} hit burst limit ({BURST_LIMIT}/{BURST_WINDOW}s)! Ignored for {IGNORE_DURATION}s")
        return False

    history.append(now)
    _user_burst[key] = history
    return True


def is_ratelimited(chat_id: int, user_id: int, is_admin: bool = False, is_command: bool = False) -> bool:
    return not _check_ratelimit(chat_id, user_id, is_admin, is_command)
