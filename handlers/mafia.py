import asyncio
import json
import logging
import os
import random
import time
from html import escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message


router = Router()
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "mafia_games.json")
STATS_FILE = os.path.join(BASE_DIR, "data", "mafia_stats.json")

PHASE_LAST_WORD = "LAST_WORD"

PHASE_IDLE = "IDLE"
PHASE_LOBBY = "LOBBY"
PHASE_NIGHT = "NIGHT"
PHASE_DISCUSSION = "DISCUSSION"
PHASE_VOTING = "VOTING"
PHASE_GAME_END = "GAME_END"

ROLE_CIVILIAN = "civilian"
ROLE_MAFIA = "mafia"
ROLE_DOCTOR = "doctor"
ROLE_COMMISSAR = "commissar"

ROLE_LABELS = {
    ROLE_CIVILIAN: "Мирный житель",
    ROLE_MAFIA: "Мафия",
    ROLE_DOCTOR: "Доктор",
    ROLE_COMMISSAR: "Комиссар",
}

PHASE_LABELS = {
    PHASE_IDLE: "игры нет",
    PHASE_LOBBY: "сбор игроков",
    PHASE_NIGHT: "ночь",
    PHASE_DISCUSSION: "обсуждение",
    PHASE_VOTING: "голосование",
    PHASE_GAME_END: "игра окончена",
    PHASE_LAST_WORD: "последнее слово",
    "ROLE_DISTRIBUTION": "раздача ролей",
}

DEFAULT_SETTINGS = {
    "min_players": 2,
    "max_players": 12,
    "doctor_min_players": 5,
    "commissar_min_players": 6,
    "night": 45,
    "discussion": 90,
    "vote": 30,
    "lobby_timeout": 10,
    "afk_enabled": True,
    "afk_limit": 3,
    "show_role_after_death": False,
    "dead_can_talk": False,
    "doctor_self_heal": True,
    "vote_change_limit": 2,
    "transfer_owner": True,
    "resend_role": True,
    "anonymous_voting": False,
    "auto_skip_night": True,
}

MAFIA_PRESETS = {
    "tiny": ("2-3 \u0438\u0433\u0440\u043e\u043a\u0430", {"min_players": 2, "max_players": 3, "doctor_min_players": 4, "commissar_min_players": 5, "night": 35, "discussion": 60, "vote": 25}),
    "small": ("4-6 \u0438\u0433\u0440\u043e\u043a\u043e\u0432", {"min_players": 3, "max_players": 6, "doctor_min_players": 5, "commissar_min_players": 6, "night": 45, "discussion": 90, "vote": 30}),
    "classic": ("\u041a\u043b\u0430\u0441\u0441\u0438\u043a\u0430 7+", {"min_players": 5, "max_players": 12, "doctor_min_players": 5, "commissar_min_players": 6, "night": 60, "discussion": 120, "vote": 45}),
}

SETTING_META = {
    "min_players": ("Минимум игроков", "Мин", 2, 20, 1),
    "max_players": ("Максимум игроков", "Макс", 2, 20, 1),
    "doctor_min_players": ("Доктор с игроков", "Док", 2, 20, 1),
    "commissar_min_players": ("Комиссар с игроков", "Ком", 2, 20, 1),
    "night": ("Время ночи", "Ночь", 15, 300, 15),
    "discussion": ("Время обсуждения", "Обс", 30, 600, 30),
    "vote": ("Время голосования", "Голос", 15, 180, 15),
    "lobby_timeout": ("Жизнь лобби", "Лобби", 1, 60, 1),
    "afk_limit": ("Пропусков до AFK", "AFK", 1, 10, 1),
    "vote_change_limit": ("Смен голоса", "Смена", 0, 10, 1),
}

TOGGLE_META = {
    "afk_enabled": "Исключать за AFK",
    "show_role_after_death": "Показывать роль после смерти",
    "dead_can_talk": "Разрешить чат мертвым",
    "doctor_self_heal": "Доктор лечит себя",
    "transfer_owner": "Передавать владельца",
    "resend_role": "Разрешить /role повторно",
    "anonymous_voting": "Скрывать голоса",
    "auto_skip_night": "Пропускать ночь по таймеру",
}

_locks: dict[int, asyncio.Lock] = {}
_file_lock = asyncio.Lock()
_timers: dict[int, asyncio.Task] = {}


def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


def _now() -> int:
    return int(time.time())


def _load_all() -> dict[str, dict[str, Any]]:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_all(data: dict[str, dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def _get_game_unlocked(chat_id: int) -> dict[str, Any] | None:
    async with _file_lock:
        data = await asyncio.to_thread(_load_all)
        return data.get(str(chat_id))


async def _put_game_unlocked(chat_id: int, game: dict[str, Any]) -> None:
    async with _file_lock:
        data = await asyncio.to_thread(_load_all)
        data[str(chat_id)] = game
        await asyncio.to_thread(_save_all, data)


async def _delete_game_unlocked(chat_id: int, preserve_settings: dict[str, Any] | None = None) -> None:
    async with _file_lock:
        data = await asyncio.to_thread(_load_all)
        if preserve_settings:
            data[str(chat_id)] = {
                "chat_id": chat_id,
                "owner": 0,
                "phase": PHASE_IDLE,
                "settings": preserve_settings,
            }
        else:
            data.pop(str(chat_id), None)
            _locks.pop(chat_id, None)
        await asyncio.to_thread(_save_all, data)


async def _get_game(chat_id: int) -> dict[str, Any] | None:
    async with _get_chat_lock(chat_id):
        return await _get_game_unlocked(chat_id)


async def _put_game(chat_id: int, game: dict[str, Any]) -> None:
    async with _get_chat_lock(chat_id):
        await _put_game_unlocked(chat_id, game)


async def _delete_game(chat_id: int, preserve_settings: dict[str, Any] | None = None) -> None:
    async with _get_chat_lock(chat_id):
        await _delete_game_unlocked(chat_id, preserve_settings)
    _cancel_timer(chat_id)




# ─── Статистика ───────────────────────────────────────────────────────────────

def _load_stats() -> dict:
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_stats(data: dict) -> None:
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _record_stats(game: dict[str, Any], winner: str) -> None:
    """Записывает победы/поражения каждого игрока по роли."""
    data = _load_stats()
    mafia_won = winner == "Мафия"
    for uid, role in game.get("roles", {}).items():
        player = game["players"].get(uid)
        if not player:
            continue
        key = str(uid)
        if key not in data:
            data[key] = {"name": player.get("name", ""), "roles": {}}
        data[key]["name"] = player.get("name", "")
        role_stats = data[key]["roles"].setdefault(role, {"wins": 0, "losses": 0})
        won = (role == ROLE_MAFIA) == mafia_won
        if won:
            role_stats["wins"] += 1
        else:
            role_stats["losses"] += 1
    _save_stats(data)

def _cancel_timer(chat_id: int) -> None:
    task = _timers.pop(chat_id, None)
    if task and not task.done():
        task.cancel()




def _schedule_reminder(bot, chat_id: int, deadline: int, phase: str) -> None:
    """Напоминание за 10 сек до конца фазы."""
    remind_at = deadline - 10
    if remind_at <= _now():
        return
    asyncio.create_task(_reminder_worker(bot, chat_id, remind_at, deadline, phase))


async def _reminder_worker(bot: Bot, chat_id: int, remind_at: int, deadline: int, phase: str) -> None:
    try:
        await asyncio.sleep(max(0, remind_at - _now()))
        game = await _get_game(chat_id)
        if not game or game.get("phase") != phase or game.get("phase_deadline") != deadline:
            return
        labels = {
            PHASE_NIGHT: "🌙 До конца ночи осталось <b>10 секунд</b>.",
            PHASE_DISCUSSION: "💬 До конца обсуждения осталось <b>10 секунд</b>.",
            PHASE_VOTING: "🗳 До конца голосования осталось <b>10 секунд</b>.",
        }
        text = labels.get(phase)
        if text:
            await bot.send_message(chat_id, text, parse_mode="HTML")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass

def _schedule_timer(bot, chat_id: int, deadline: int, phase: str) -> None:
    _cancel_timer(chat_id)
    _timers[chat_id] = asyncio.create_task(_timer_worker(bot, chat_id, deadline, phase))
    _schedule_reminder(bot, chat_id, deadline, phase)


async def _timer_worker(bot: Bot, chat_id: int, deadline: int, phase: str) -> None:
    try:
        await asyncio.sleep(max(0, deadline - _now()))
        async with _get_chat_lock(chat_id):
            game = await _get_game_unlocked(chat_id)
            if not game or game.get("phase") != phase or game.get("phase_deadline") != deadline:
                return
            if phase == PHASE_LOBBY:
                await _delete_game_unlocked(chat_id, game.get("settings"))
                _cancel_timer(chat_id)
                await bot.send_message(chat_id, "⌛ Лобби мафии закрыто: игра не началась вовремя.")
            elif phase == PHASE_NIGHT:
                await _process_night_internal(bot, chat_id)
            elif phase == PHASE_DISCUSSION:
                await _start_vote_internal(bot, chat_id)
            elif phase == PHASE_VOTING:
                await _process_vote_internal(bot, chat_id)
    except asyncio.CancelledError:
        pass
    finally:
        current_task = asyncio.current_task()
        if _timers.get(chat_id) is current_task:
            _timers.pop(chat_id, None)


def _mention(player: dict[str, Any]) -> str:
    name = escape(player.get("name") or "Игрок")
    return f'<a href="tg://user?id={player["id"]}">{name}</a>'


def _phase_label(game: dict[str, Any]) -> str:
    return PHASE_LABELS.get(game.get("phase"), str(game.get("phase", "игра")))


def _deadline_line(game: dict[str, Any]) -> str:
    deadline = game.get("phase_deadline")
    if not deadline:
        return ""
    left = max(0, int(deadline) - _now())
    if left >= 60:
        return f"Осталось: <b>{left // 60} мин {left % 60:02d} сек</b>"
    return f"Осталось: <b>{left} сек</b>"


def _ready_progress(game: dict[str, Any]) -> str:
    players = list(game.get("players", {}).values())
    ready = sum(1 for player in players if player.get("ready"))
    total = len(players)
    if total == 0:
        return "Готовы: <b>0 из 0</b>"
    filled = round((ready / total) * 8)
    bar = "●" * filled + "○" * (8 - filled)
    return f"Готовы: <b>{ready} из {total}</b>  {bar}"


def _alive_count(game: dict[str, Any], role: str | None = None) -> int:
    ids = _alive_ids(game)
    if role is None:
        return len(ids)
    return sum(1 for uid in ids if _role(game, uid) == role)


def _action_hint(game: dict[str, Any]) -> str:
    phase = game.get("phase")
    if phase == PHASE_LOBBY:
        return "Нажми <b>Войти</b>, потом <b>Готов</b>. Владелец запускает игру кнопкой <b>Начать</b>."
    if phase == PHASE_NIGHT:
        return "Активные роли выбирают действие в личных сообщениях."
    if phase == PHASE_DISCUSSION:
        return "Обсуждайте подозреваемых. Бот не подсказывает и не анализирует."
    if phase == PHASE_VOTING:
        return "Голосуй кнопкой ниже. Голос можно изменить, если это разрешено настройками."
    return ""


def _alive_ids(game: dict[str, Any]) -> list[str]:
    return [str(uid) for uid in game.get("alive", [])]


def _is_bot_player(game: dict[str, Any], user_id: int | str) -> bool:
    player = game.get("players", {}).get(str(user_id))
    return player.get("is_bot", False) if player else False


def _player(game: dict[str, Any], user_id: int | str) -> dict[str, Any] | None:
    return game.get("players", {}).get(str(user_id))


def _is_alive(game: dict[str, Any], user_id: int | str) -> bool:
    return str(user_id) in set(_alive_ids(game))


def _role(game: dict[str, Any], user_id: int | str) -> str | None:
    return game.get("roles", {}).get(str(user_id))


def _can_start_lobby(game: dict[str, Any]) -> tuple[bool, str]:
    settings = _ensure_settings(game)
    players = list(game.get("players", {}).values())
    if len(players) < settings["min_players"]:
        return False, "\u043c\u0430\u043b\u043e \u0438\u0433\u0440\u043e\u043a\u043e\u0432"
    if not players or not all(player.get("ready") for player in players):
        return False, "\u043d\u0435 \u0432\u0441\u0435 \u0433\u043e\u0442\u043e\u0432\u044b"
    if any(player.get("dm_ok") is False for player in players if not player.get("is_bot")):
        return False, "\u043f\u0440\u043e\u0432\u0435\u0440\u044c \u041b\u0421"
    return True, "\u0433\u043e\u0442\u043e\u0432\u043e"


def _lobby_keyboard(game: dict[str, Any]) -> InlineKeyboardMarkup:
    can_start, reason = _can_start_lobby(game)
    start_text = "\u25b6 \u041d\u0430\u0447\u0430\u0442\u044c \u0438\u0433\u0440\u0443" if can_start else f"\u25b6 \u041d\u0430\u0447\u0430\u0442\u044c: {reason}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2795 \u0412\u043e\u0439\u0442\u0438", callback_data="maf:join"),
         InlineKeyboardButton(text="\u2705 \u0413\u043e\u0442\u043e\u0432", callback_data="maf:ready")],
        [InlineKeyboardButton(text="\U0001f510 \u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u041b\u0421", callback_data="maf:checkdm"),
         InlineKeyboardButton(text=start_text, callback_data="maf:start")],
        [InlineKeyboardButton(text="\U0001f465 \u0418\u0433\u0440\u043e\u043a\u0438", callback_data="maf:players"),
         InlineKeyboardButton(text="\u2796 \u0412\u044b\u0439\u0442\u0438", callback_data="maf:leave")],
        [InlineKeyboardButton(text="\u274c \u0417\u0430\u043a\u0440\u044b\u0442\u044c \u043b\u043e\u0431\u0431\u0438", callback_data="maf:cancel")],
    ])


def _target_keyboard(game: dict[str, Any], action: str, actor_id: int | str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for uid in _alive_ids(game):
        player = _player(game, uid)
        if not player:
            continue
        rows.append([InlineKeyboardButton(
            text=player.get("name") or f"Игрок {uid}",
            callback_data=f"maf:{action}:{uid}",
        )])
    rows.append([InlineKeyboardButton(text="⏭ Пропустить действие", callback_data=f"maf:skip:{actor_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _vote_keyboard(game: dict[str, Any]) -> InlineKeyboardMarkup:
    rows = []
    for uid in _alive_ids(game):
        player = _player(game, uid)
        if player:
            rows.append([InlineKeyboardButton(
                text=player.get("name") or f"Игрок {uid}",
                callback_data=f"maf:vote:{uid}",
            )])
    rows.append([InlineKeyboardButton(text="⏭ Воздержаться", callback_data="maf:vote:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _demo_keyboard(labels: list[str], width: int = 2) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for label in labels:
        row.append(InlineKeyboardButton(text=label, callback_data="maf:noop"))
        if len(row) == width:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _demo_game(chat_id: int, owner_id: int, owner_name: str) -> dict[str, Any]:
    now = _now()
    players = {
        str(owner_id): {
            "id": owner_id,
            "name": owner_name,
            "username": None,
            "joined_at": now,
            "ready": True,
            "afk": 0,
            "last_doctor_self_heal": False,
        },
        "10001": {"id": 10001, "name": "Алиса", "username": None, "is_bot": False, "joined_at": now + 1, "ready": True, "afk": 0, "last_doctor_self_heal": False},
        "10002": {"id": 10002, "name": "Борис", "username": None, "is_bot": False, "joined_at": now + 2, "ready": False, "afk": 0, "last_doctor_self_heal": False},
        "10003": {"id": 10003, "name": "Кира", "username": None, "is_bot": False, "joined_at": now + 3, "ready": True, "afk": 0, "last_doctor_self_heal": False},
    }
    ids = list(players.keys())
    return {
        "chat_id": chat_id,
        "owner": owner_id,
        "phase": PHASE_LOBBY,
        "phase_deadline": now + 540,
        "night": 1,
        "settings": dict(DEFAULT_SETTINGS),
        "players": players,
        "roles": {
            ids[0]: ROLE_CIVILIAN,
            ids[1]: ROLE_MAFIA,
            ids[2]: ROLE_DOCTOR,
            ids[3]: ROLE_COMMISSAR,
        },
        "alive": ids,
        "dead": {},
        "votes": {},
        "vote_changes": {},
        "night_actions": {},
        "skips": [],
        "last_night": {},
    }


def _night_action_text(game: dict[str, Any], role: str, mafia_names: str = "") -> str:
    left = max(0, game.get("phase_deadline", _now()) - _now())
    if role == ROLE_MAFIA:
        return (
            "🌙 <b>Ночь. Ход мафии</b>\n\n"
            f"Союзники: <b>{escape(mafia_names)}</b>\n"
            "Выбери, кого убрать этой ночью.\n"
            "Если мафий несколько, сработает большинство голосов.\n\n"
            f"Время на выбор: <b>{left} сек</b>"
        )
    if role == ROLE_DOCTOR:
        return (
            "🌙 <b>Ночь. Ход доктора</b>\n\n"
            "Выбери, кого лечить этой ночью.\n"
            "Себя нельзя лечить два раза подряд.\n\n"
            f"Время на выбор: <b>{left} сек</b>"
        )
    if role == ROLE_COMMISSAR:
        return (
            "🌙 <b>Ночь. Ход комиссара</b>\n\n"
            "Выбери игрока для проверки.\n"
            "Ответ придет только тебе.\n\n"
            f"Время на выбор: <b>{left} сек</b>"
        )
    return ""


def _ensure_settings(game: dict[str, Any]) -> dict[str, Any]:
    settings = game.setdefault("settings", {})
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)
    return settings


def _settings_keyboard(game: dict[str, Any]) -> InlineKeyboardMarkup:
    settings = _ensure_settings(game)
    rows = [[InlineKeyboardButton(text="2-3", callback_data="maf:preset:tiny"),
             InlineKeyboardButton(text="4-6", callback_data="maf:preset:small"),
             InlineKeyboardButton(text="7+", callback_data="maf:preset:classic")]]
    for key, (label, _short_label, _min_value, _max_value, _step) in SETTING_META.items():
        value = settings[key]
        unit = " сек." if key in {"night", "discussion", "vote"} else " мин." if key == "lobby_timeout" else ""
        rows.append([InlineKeyboardButton(text=f"{label}: {value}{unit}", callback_data="maf:noop")])
        rows.append([
            InlineKeyboardButton(text="−", callback_data=f"maf:set:{key}:-"),
            InlineKeyboardButton(text="+", callback_data=f"maf:set:{key}:+"),
        ])
    for key, label in TOGGLE_META.items():
        value = "Да" if settings[key] else "Нет"
        rows.append([InlineKeyboardButton(text=f"{label}: {value}", callback_data=f"maf:toggle:{key}")])
    rows.append([InlineKeyboardButton(text="♻ Сброс", callback_data="maf:resetsettings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _settings_text(game: dict[str, Any]) -> str:
    settings = _ensure_settings(game)
    bool_label = lambda value: "Да" if value else "Нет"
    return (
        "⚙ <b>Настройки мафии</b>\n\n"
        "<b>Игроки и время</b>\n"
        f"Минимум игроков: <b>{settings['min_players']}</b>\n"
        f"Максимум игроков: <b>{settings['max_players']}</b>\n"
        f"Доктор появляется с: <b>{settings.get('doctor_min_players', 5)}</b> игроков\n"
        f"Комиссар появляется с: <b>{settings.get('commissar_min_players', 6)}</b> игроков\n"
        f"Ночь длится: <b>{settings['night']} сек</b>\n"
        f"Обсуждение длится: <b>{settings['discussion']} сек</b>\n"
        f"Голосование длится: <b>{settings['vote']} сек</b>\n"
        f"Лобби закрывается через: <b>{settings['lobby_timeout']} мин</b>\n\n"
        "<b>Правила игры</b>\n"
        f"AFK-исключение: <b>{bool_label(settings['afk_enabled'])}</b>"
        f" после <b>{settings['afk_limit']}</b> пропусков\n"
        f"Сменить голос можно: <b>{settings['vote_change_limit']}</b> раз\n"
        f"Доктор может лечить себя: <b>{bool_label(settings['doctor_self_heal'])}</b>\n"
        f"Голоса анонимные: <b>{bool_label(settings['anonymous_voting'])}</b>\n\n"
        "<b>Поведение бота</b>\n"
        f"Показывать роль после смерти: <b>{bool_label(settings['show_role_after_death'])}</b>\n"
        f"Мертвые могут писать: <b>{bool_label(settings['dead_can_talk'])}</b>\n"
        f"Передавать владельца лобби: <b>{bool_label(settings['transfer_owner'])}</b>\n"
        f"Повторно отправлять роль: <b>{bool_label(settings['resend_role'])}</b>\n"
        f"Автопропуск ночью: <b>{bool_label(settings['auto_skip_night'])}</b>"
    )


def _new_game(chat_id: int, owner: Message, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    user = owner.from_user
    uid = str(user.id)
    merged_settings = dict(DEFAULT_SETTINGS)
    if settings:
        merged_settings.update(settings)
    return {
        "chat_id": chat_id,
        "owner": user.id,
        "phase": PHASE_LOBBY,
        "phase_deadline": _now() + DEFAULT_SETTINGS["lobby_timeout"] * 60,
        "night": 0,
        "settings": merged_settings,
        "players": {
            uid: {
                "id": user.id,
                "name": user.full_name,
                "username": user.username,
                "is_bot": user.is_bot or False,
                "joined_at": _now(),
                "ready": False,
                "afk": 0,
                "last_doctor_self_heal": False,
                "dm_ok": None,
            }
        },
        "lobby_message_id": None,
        "roles": {},
        "alive": [],
        "dead": {},
        "votes": {},
        "vote_changes": {},
        "night_actions": {},
        "skips": [],
        "last_night": {},
    }


def _role_counts_for_total(total: int, settings: dict[str, Any]) -> dict[str, int]:
    if total <= 0:
        return {ROLE_MAFIA: 0, ROLE_DOCTOR: 0, ROLE_COMMISSAR: 0, ROLE_CIVILIAN: 0}
    mafia = max(1, total // 4)
    cursor = mafia
    doctor = 1 if total >= int(settings.get("doctor_min_players", 5)) and cursor < total else 0
    cursor += doctor
    commissar = 1 if total >= int(settings.get("commissar_min_players", 6)) and cursor < total else 0
    cursor += commissar
    civilian = max(0, total - cursor)
    return {ROLE_MAFIA: mafia, ROLE_DOCTOR: doctor, ROLE_COMMISSAR: commissar, ROLE_CIVILIAN: civilian}


def _roles_preview(total: int, settings: dict[str, Any]) -> str:
    counts = _role_counts_for_total(total, settings)
    parts = [f"\U0001f3ad \u043c\u0430\u0444\u0438\u044f {counts[ROLE_MAFIA]}"]
    if counts[ROLE_DOCTOR]:
        parts.append(f"\U0001f48a \u0434\u043e\u043a\u0442\u043e\u0440 {counts[ROLE_DOCTOR]}")
    if counts[ROLE_COMMISSAR]:
        parts.append(f"\U0001f50e \u043a\u043e\u043c\u0438\u0441\u0441\u0430\u0440 {counts[ROLE_COMMISSAR]}")
    if counts[ROLE_CIVILIAN]:
        parts.append(f"\U0001f464 \u043c\u0438\u0440\u043d\u044b\u0435 {counts[ROLE_CIVILIAN]}")
    return " | ".join(parts)


def _player_dm_icon(player: dict[str, Any]) -> str:
    if player.get("is_bot"):
        return "\U0001f916"
    if player.get("dm_ok") is True:
        return "\U0001f510\u2705"
    if player.get("dm_ok") is False:
        return "\U0001f510\u26a0\ufe0f"
    return "\U0001f510?"


def _format_lobby(game: dict[str, Any]) -> str:
    players = sorted(game["players"].values(), key=lambda p: p["joined_at"])
    settings = _ensure_settings(game)
    total = len(players)
    missing_players = max(0, settings["min_players"] - total)
    lines = [
        "🎭 <b>Мафия</b>",
        "<i>Собираем игроков</i>",
        "",
        f"Игроки в лобби: <b>{total}/{settings['max_players']}</b>",
        f"Минимум для старта: <b>{settings['min_players']}</b>",
        _ready_progress(game),
    ]
    if missing_players:
        suffix = "игрок" if missing_players == 1 else "игрока" if missing_players in {2, 3, 4} else "игроков"
        lines.append(f"До старта не хватает: <b>{missing_players} {suffix}</b>")
    elif not all(player.get("ready") for player in players):
        lines.append(f"Стартуют сейчас: <b>{total}</b> игроков, когда все нажмут <b>Готов</b>.")
    else:
        lines.append(f"Можно начинать: стартуют <b>{total}</b> игроков.")
    if total:
        lines.append(f"Роли при старте: <b>{_roles_preview(total, settings)}</b>")
    deadline = _deadline_line(game)
    if deadline:
        lines.append(deadline)
    lines.append("")
    lines.append("<b>Участники</b>")
    for player in players:
        owner = "  👑 ведущий" if player["id"] == game["owner"] else ""
        ready = "✅" if player.get("ready") else "▫️"
        dm = _player_dm_icon(player)
        lines.append(f"{ready} {dm} {_mention(player)}{owner}")
    lines.append("")
    lines.append(_action_hint(game))
    return "\n".join(lines)


def _format_status(game: dict[str, Any]) -> str:
    alive = [_mention(game["players"][uid]) for uid in _alive_ids(game) if uid in game["players"]]
    dead = [_mention(game["players"][uid]) for uid in game.get("dead", {}) if uid in game["players"]]
    deadline = _deadline_line(game)
    lines = [
        "📊 <b>Мафия: статус</b>",
        "",
        f"Фаза: <b>{_phase_label(game)}</b>",
        f"Ночь: <b>{game.get('night', 0)}</b>",
        f"Живых: <b>{len(alive)}</b>  |  Мертвых: <b>{len(dead)}</b>",
        f"Мафия в живых: <b>{_alive_count(game, ROLE_MAFIA)}</b>",
    ]
    if deadline:
        lines.append(deadline)
    lines.extend([
        "",
        "<b>Живые</b>",
        ", ".join(alive) if alive else "нет",
        "",
        "<b>Выбыли</b>",
        ", ".join(dead) if dead else "нет",
    ])
    hint = _action_hint(game)
    if hint:
        lines.extend(["", hint])
    return "\n".join(lines)


async def _is_user_admin(bot, chat_id: int, user_id: int) -> bool:
    if chat_id > 0:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {"creator", "administrator"}
    except Exception:
        return False


async def _can_control(bot, game: dict[str, Any], user_id: int) -> bool:
    return user_id == game.get("owner") or await _is_user_admin(bot, game["chat_id"], user_id)


async def _require_game(event: Message | CallbackQuery) -> dict[str, Any] | None:
    chat_id, game = await _game_for_event(event)
    if not game or game.get("phase") == PHASE_GAME_END:
        message = event.message if isinstance(event, CallbackQuery) else event
        await message.reply("Сейчас нет активной игры. Создать: /mafia")
        return None
    return game


async def _game_for_event(event: Message | CallbackQuery) -> tuple[int | None, dict[str, Any] | None]:
    message = event.message if isinstance(event, CallbackQuery) else event
    if message.chat.type == "private":
        chat_id = await _find_user_game(event.from_user.id)
        if chat_id is None:
            return None, None
        return chat_id, await _get_game(chat_id)
    return message.chat.id, await _get_game(message.chat.id)


async def _find_user_game(user_id: int) -> int | None:
    data = await asyncio.to_thread(_load_all)
    for game in data.values():
        if game.get("phase") not in {PHASE_IDLE, PHASE_GAME_END} and str(user_id) in game.get("players", {}):
            return game["chat_id"]
    return None


def _find_target(game: dict[str, Any], query: str) -> str | None:
    needle = query.strip().lstrip("@").lower()
    if not needle:
        return None
    for uid in _alive_ids(game):
        player = game["players"].get(uid, {})
        names = {
            str(player.get("id", "")),
            (player.get("name") or "").lower(),
            (player.get("username") or "").lower(),
        }
        if needle in names:
            return uid
    partial = []
    for uid in _alive_ids(game):
        player = game["players"].get(uid, {})
        haystack = " ".join([
            player.get("name") or "",
            player.get("username") or "",
        ]).lower()
        if needle and needle in haystack:
            partial.append(uid)
    return partial[0] if len(partial) == 1 else None


def _command_args(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


async def _send_lobby(event: Message | CallbackQuery, game: dict[str, Any]) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    text = _format_lobby(game)
    markup = _lobby_keyboard(game)
    sent = None
    if isinstance(event, CallbackQuery):
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            game["lobby_message_id"] = message.message_id
            await _put_game(message.chat.id, game)
            return
        except Exception:
            pass
    message_id = game.get("lobby_message_id")
    if message_id:
        try:
            await message.bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode="HTML",
            )
            return
        except Exception:
            game["lobby_message_id"] = None
    sent = await message.answer(text, reply_markup=markup, parse_mode="HTML")
    game["lobby_message_id"] = sent.message_id
    await _put_game(message.chat.id, game)


async def _check_player_dm(bot: Bot, player: dict[str, Any], notify: bool = False) -> bool:
    if player.get("is_bot"):
        player["dm_ok"] = True
        return True
    try:
        text = "\U0001f510 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u041b\u0421 \u0434\u043b\u044f \u0438\u0433\u0440\u044b \u00ab\u041c\u0430\u0444\u0438\u044f\u00bb \u043f\u0440\u043e\u0439\u0434\u0435\u043d\u0430."
        if notify:
            text += " \u0422\u0435\u043f\u0435\u0440\u044c \u0431\u043e\u0442 \u0441\u043c\u043e\u0436\u0435\u0442 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0442\u0435\u0431\u0435 \u0440\u043e\u043b\u044c \u0438 \u043d\u043e\u0447\u043d\u044b\u0435 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f."
        await bot.send_message(player["id"], text)
        player["dm_ok"] = True
        return True
    except Exception:
        player["dm_ok"] = False
        return False


async def _join_player(event: Message | CallbackQuery) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    user = event.from_user
    game = await _get_game(message.chat.id)
    if not game or game.get("phase") != PHASE_LOBBY:
        await message.reply("Лобби нет. Создать игру: /mafia")
        return
    uid = str(user.id)
    if uid in game["players"]:
        await message.reply("Ты уже в лобби.")
        return
    if len(game["players"]) >= game["settings"]["max_players"]:
        await message.reply("Лобби заполнено.")
        return
    game["players"][uid] = {
        "id": user.id,
        "name": user.full_name,
        "username": user.username,
        "is_bot": user.is_bot or False,
        "joined_at": _now(),
        "ready": False,
        "afk": 0,
        "last_doctor_self_heal": False,
        "dm_ok": None,
    }
    await _put_game(message.chat.id, game)
    await _send_lobby(event, game)


async def _leave_player(event: Message | CallbackQuery) -> None:
    chat_id, game = await _game_for_event(event)
    message = event.message if isinstance(event, CallbackQuery) else event
    user = event.from_user
    if not game:
        await message.reply("Игры нет.")
        return
    uid = str(user.id)
    if uid not in game["players"]:
        await message.reply("Ты не участвуешь в игре.")
        return
    if game["phase"] == PHASE_LOBBY:
        game["players"].pop(uid, None)
        if not game["players"]:
            await _delete_game(chat_id, game.get("settings"))
            await message.reply("Лобби закрыто: игроков не осталось.")
            return
        if game["owner"] == user.id and game["settings"]["transfer_owner"]:
            first = sorted(game["players"].values(), key=lambda p: p["joined_at"])[0]
            game["owner"] = first["id"]
        await _put_game(chat_id, game)
        await _send_lobby(event, game)
        return
    if _is_alive(game, uid):
        _kill_player(game, uid)
        await _put_game(chat_id, game)
        await message.reply(f"{_mention(game['players'][uid])} вышел из группы и считается погибшим.", parse_mode="HTML")
        await _check_or_continue(message.bot, chat_id, game)


async def _ready_player(event: Message | CallbackQuery) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    user = event.from_user
    game = await _get_game(message.chat.id)
    if not game or game.get("phase") != PHASE_LOBBY:
        await message.reply("Готовность доступна только в лобби.")
        return
    uid = str(user.id)
    if uid not in game["players"]:
        await message.reply("Сначала войди в игру: /join")
        return
    game["players"][uid]["ready"] = not game["players"][uid].get("ready", False)
    await _put_game(message.chat.id, game)
    await _send_lobby(event, game)


async def _start_game(event: Message | CallbackQuery) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    user = event.from_user
    bot = event.bot
    game = await _get_game(message.chat.id)
    if not game or game.get("phase") != PHASE_LOBBY:
        await message.reply("Лобби нет.")
        return
    if not await _can_control(bot, game, user.id):
        await message.reply("Начать игру может владелец лобби или администратор.")
        return
    players = game["players"]
    if len(players) < game["settings"]["min_players"]:
        logger.warning("Start blocked: not enough players (%d/%d) in chat %d",
                       len(players), game["settings"]["min_players"], message.chat.id)
        await message.reply(
            f"Пока рано начинать.\n\n"
            f"Игроков: <b>{len(players)}/{game['settings']['min_players']}</b>\n"
            "Позови еще людей или уменьши <b>Минимум игроков</b> в /settings.",
            parse_mode="HTML",
        )
        return
    if not all(player.get("ready") for player in players.values()):
        not_ready = [player.get("name") or str(player["id"]) for player in players.values() if not player.get("ready")]
        logger.warning("Start blocked: not all ready in chat %d, waiting for: %s", message.chat.id, not_ready)
        waiting = [_mention(player) for player in players.values() if not player.get("ready")]
        await message.reply(
            "Не все готовы.\n\n"
            "Ждем:\n" + "\n".join(waiting) + "\n\n"
            "Каждый игрок должен нажать <b>Я готов</b> или написать /ready.",
            parse_mode="HTML",
        )
        return
    closed_dm = []
    for player in players.values():
        if player.get("is_bot"):
            continue
        try:
            await bot.send_message(player["id"], "Проверка ЛС для игры «Мафия» пройдена.")
        except Exception:
            closed_dm.append(player.get("name") or str(player["id"]))
    if closed_dm:
        logger.warning("Start blocked: closed DMs in chat %d, players: %s", message.chat.id, closed_dm)
        await message.reply(
            "Не могу начать игру: у некоторых игроков закрыты личные сообщения с ботом.\n\n"
            + "\n".join(f"• {escape(name)}" for name in closed_dm)
            + "\n\nКаждый должен открыть бота в ЛС и нажать Start.",
            parse_mode="HTML",
        )
        return
    _assign_roles(game)
    logger.info("Game started in chat %d with %d players", message.chat.id, len(players))
    game["phase"] = "ROLE_DISTRIBUTION"
    game["alive"] = list(players.keys())
    game["dead"] = {}
    await _put_game(message.chat.id, game)
    for uid, role in game["roles"].items():
        if _is_bot_player(game, uid):
            await bot.send_message(
                chat_id,
                f"🎭 {_mention(game['players'][uid])}, твоя роль: <b>{ROLE_LABELS[role]}</b>",
                parse_mode="HTML",
            )
        else:
            await bot.send_message(int(uid), _role_text(role), parse_mode="HTML")
    await message.reply(
        "🎭 <b>Роли розданы</b>\n\n"
        "Проверьте личные сообщения с ботом. Игра начинается.",
        parse_mode="HTML",
    )
    await _start_night(bot, message.chat.id, game)


def _assign_roles(game: dict[str, Any]) -> None:
    ids = list(game["players"].keys())
    random.shuffle(ids)
    total = len(ids)
    mafia_count = max(1, total // 4)
    roles: dict[str, str] = {}
    for uid in ids[:mafia_count]:
        roles[uid] = ROLE_MAFIA
    cursor = mafia_count
    settings = game.get("settings", DEFAULT_SETTINGS)
    doctor_min_players = int(settings.get("doctor_min_players", 5))
    commissar_min_players = int(settings.get("commissar_min_players", 6))
    if total >= doctor_min_players and cursor < total:
        roles[ids[cursor]] = ROLE_DOCTOR
        cursor += 1
    if total >= commissar_min_players and cursor < total:
        roles[ids[cursor]] = ROLE_COMMISSAR
        cursor += 1
    for uid in ids:
        roles.setdefault(uid, ROLE_CIVILIAN)
    game["roles"] = roles


def _role_text(role: str) -> str:
    if role == ROLE_MAFIA:
        return (
            "🎭 <b>Твоя роль: Мафия</b>\n\n"
            "Цель: убрать мирных жителей и сравняться с ними по числу.\n"
            "Ночью выбирай жертву кнопкой в личных сообщениях.\n"
            "Днем не выдавай себя и голосуй в группе."
        )
    if role == ROLE_DOCTOR:
        return (
            "🎭 <b>Твоя роль: Доктор</b>\n\n"
            "Цель: помочь мирным найти мафию.\n"
            "Ночью выбирай игрока, которого хочешь спасти.\n"
            "Себя нельзя лечить два раза подряд."
        )
    if role == ROLE_COMMISSAR:
        return (
            "🎭 <b>Твоя роль: Комиссар</b>\n\n"
            "Цель: помочь мирным найти мафию.\n"
            "Ночью проверяй одного игрока.\n"
            "Результат проверки увидишь только ты."
        )
    return (
        "🎭 <b>Твоя роль: Мирный житель</b>\n\n"
        "Цель: вычислить мафию на обсуждении и голосовании.\n"
        "Ночных действий нет. Слушай, спорь, голосуй."
    )


async def _start_night(bot, chat_id: int, game: dict[str, Any]) -> None:
    async with _get_chat_lock(chat_id):
        await _start_night_internal(bot, chat_id, game)


async def _start_night_internal(bot, chat_id: int, game: dict[str, Any]) -> None:
    if game.get("phase") == PHASE_NIGHT:
        return
    game["phase"] = PHASE_NIGHT
    game["night"] = game.get("night", 0) + 1
    game["phase_deadline"] = _now() + game["settings"]["night"]
    game["night_actions"] = {"mafia": {}, "doctor": None, "commissar": None}
    game["skips"] = []
    await _put_game_unlocked(chat_id, game)
    _schedule_timer(bot, chat_id, game["phase_deadline"], PHASE_NIGHT)
    await bot.send_message(
        chat_id,
        f"🌙 <b>Ночь {game['night']}</b>\n\n"
        "Город засыпает. Активные роли получили действия в личные сообщения.\n"
        f"На ход есть <b>{game['settings']['night']} сек</b>.",
        parse_mode="HTML",
    )
    mafia_ids = [uid for uid in _alive_ids(game) if _role(game, uid) == ROLE_MAFIA]
    mafia_names = ", ".join(
        escape(game["players"][uid]["name"])
        for uid in mafia_ids if uid in game["players"]
    )
    for uid in _alive_ids(game):
        role = _role(game, uid)
        player = game["players"].get(uid, {})
        is_bot_player = player.get("is_bot", False)
        if role == ROLE_MAFIA:
            if is_bot_player:
                await bot.send_message(
                    chat_id,
                    f"🎭 <b>Ночной ход для {escape(player.get('name') or 'Бот')}</b>\n\n"
                    "Выбери, кого убрать этой ночью.",
                    reply_markup=_target_keyboard(game, "kill", uid),
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    int(uid),
                    _night_action_text(game, ROLE_MAFIA, mafia_names),
                    reply_markup=_target_keyboard(game, "kill", uid),
                    parse_mode="HTML",
                )
        elif role == ROLE_DOCTOR:
            if is_bot_player:
                await bot.send_message(
                    chat_id,
                    f"🎭 <b>Ночной ход для {escape(player.get('name') or 'Бот')}</b>\n\n"
                    "Выбери, кого лечить этой ночью.",
                    reply_markup=_target_keyboard(game, "heal", uid),
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    int(uid),
                    _night_action_text(game, ROLE_DOCTOR),
                    reply_markup=_target_keyboard(game, "heal", uid),
                    parse_mode="HTML",
                )
        elif role == ROLE_COMMISSAR:
            if is_bot_player:
                await bot.send_message(
                    chat_id,
                    f"🎭 <b>Ночной ход для {escape(player.get('name') or 'Бот')}</b>\n\n"
                    "Выбери игрока для проверки.",
                    reply_markup=_target_keyboard(game, "check", uid),
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    int(uid),
                    _night_action_text(game, ROLE_COMMISSAR),
                    reply_markup=_target_keyboard(game, "check", uid),
                    parse_mode="HTML",
                )


async def _record_night_action(call: CallbackQuery, action: str, target_id: str | None) -> None:
    chat_id, _ = await _game_for_event(call)
    if chat_id is None:
        await call.answer("Активная игра не найдена.", show_alert=True)
        return

    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game:
            await call.answer("Активная игра не найдена.", show_alert=True)
            return

        uid = str(call.from_user.id)
        if game.get("phase") != PHASE_NIGHT or not _is_alive(game, uid):
            await call.answer("Сейчас не твоя ночная фаза.", show_alert=True)
            return

        role = _role(game, uid)
        if action == "kill" and role != ROLE_MAFIA:
            await call.answer("Это действие доступно только мафии.", show_alert=True)
            return
        if action == "heal" and role != ROLE_DOCTOR:
            await call.answer("Это действие доступно только доктору.", show_alert=True)
            return
        if action == "check" and role != ROLE_COMMISSAR:
            await call.answer("Это действие доступно только комиссару.", show_alert=True)
            return
        if target_id and target_id not in _alive_ids(game):
            await call.answer("Цель уже недоступна.", show_alert=True)
            return
        if action == "heal" and target_id == uid and not game["settings"]["doctor_self_heal"]:
            await call.answer("Самолечение отключено настройками.", show_alert=True)
            return
        if action == "heal" and target_id == uid and game["players"][uid].get("last_doctor_self_heal"):
            await call.answer("Нельзя лечить себя два раза подряд.", show_alert=True)
            return

        if target_id is None:
            game.setdefault("skips", [])
            if uid not in game["skips"]:
                game["skips"].append(uid)
        elif action == "kill":
            game["night_actions"]["mafia"][uid] = target_id
        elif action == "heal":
            game["night_actions"]["doctor"] = target_id
        elif action == "check":
            game["night_actions"]["commissar"] = target_id
            result = "МАФИЯ" if _role(game, target_id) == ROLE_MAFIA else "НЕ МАФИЯ"
            await call.message.answer(
                f"🔎 <b>Проверка завершена</b>\n\n"
                f"{escape(game['players'][target_id]['name'])}: <b>{result}</b>",
                parse_mode="HTML",
            )

        await _put_game_unlocked(chat_id, game)
        await call.answer("Принято.")
        if target_id:
            await call.message.edit_text("✅ Действие принято. Ждем остальных игроков.")

        if _night_ready(game):
            await _process_night_internal(call.bot, chat_id)


def _night_ready(game: dict[str, Any]) -> bool:
    alive = _alive_ids(game)
    mafia_ids = [uid for uid in alive if _role(game, uid) == ROLE_MAFIA]
    doctor_ids = [uid for uid in alive if _role(game, uid) == ROLE_DOCTOR]
    commissar_ids = [uid for uid in alive if _role(game, uid) == ROLE_COMMISSAR]
    skips = set(game.get("skips", []))
    actions = game.get("night_actions", {})
    mafia_done = all(uid in actions.get("mafia", {}) or uid in skips for uid in mafia_ids)
    doctor_done = not doctor_ids or actions.get("doctor") or doctor_ids[0] in skips
    commissar_done = not commissar_ids or actions.get("commissar") or commissar_ids[0] in skips
    return mafia_done and doctor_done and commissar_done


# FIX: возвращает list[str] вместо None
def _apply_night_afk(game: dict[str, Any]) -> list[str]:
    alive = _alive_ids(game)
    actions = game.get("night_actions", {})
    skips = set(game.get("skips", []))
    acted = set(actions.get("mafia", {}).keys()) | skips
    if actions.get("doctor"):
        doctor_ids = [uid for uid in alive if _role(game, uid) == ROLE_DOCTOR]
        if doctor_ids:
            acted.add(doctor_ids[0])
    if actions.get("commissar"):
        commissar_ids = [uid for uid in alive if _role(game, uid) == ROLE_COMMISSAR]
        if commissar_ids:
            acted.add(commissar_ids[0])
    for uid in alive:
        if _role(game, uid) in {ROLE_MAFIA, ROLE_DOCTOR, ROLE_COMMISSAR} and uid not in acted:
            game["players"][uid]["afk"] = game["players"][uid].get("afk", 0) + 1
    return _exclude_afk(game)


# FIX: синхронная функция, убран async def
def _kill_player(game: dict[str, Any], user_id: str) -> None:
    uid = str(user_id)
    if uid in game.get("alive", []):
        game["alive"].remove(uid)
    game.setdefault("dead", {})[uid] = {"role": _role(game, uid), "at": _now()}


def _exclude_afk(game: dict[str, Any]) -> list[str]:
    if not game["settings"]["afk_enabled"]:
        return []
    removed = []
    limit = game["settings"]["afk_limit"]
    for uid in list(_alive_ids(game)):
        if game["players"][uid].get("afk", 0) >= limit:
            if uid in game["alive"]:
                game["alive"].remove(uid)
            game.setdefault("dead", {})[uid] = {"role": _role(game, uid), "at": _now(), "reason": "AFK"}
            removed.append(uid)
    return removed


async def _process_night_internal(bot: Bot, chat_id: int) -> None:
    _cancel_timer(chat_id)
    game = await _get_game_unlocked(chat_id)
    if not game or game.get("phase") != PHASE_NIGHT:
        return

    actions = game.get("night_actions", {})
    mafia_votes = list(actions.get("mafia", {}).values())
    kill_target = None
    if mafia_votes:
        counts = {uid: mafia_votes.count(uid) for uid in set(mafia_votes)}
        if counts:
            top_count = max(counts.values())
            kill_target = random.choice([uid for uid, count in counts.items() if count == top_count])

    healed = actions.get("doctor")

    # FIX: _apply_night_afk теперь возвращает list[str]
    afk_removed = []
    if game["settings"]["afk_enabled"]:
        afk_removed = _apply_night_afk(game)

    for uid, player in game["players"].items():
        if _role(game, uid) == ROLE_DOCTOR:
            player["last_doctor_self_heal"] = bool(healed == uid)

    killed_by_mafia = False
    if kill_target and kill_target != healed and _is_alive(game, kill_target):
        _kill_player(game, kill_target)
        killed_by_mafia = True

    lines = ["☀️ <b>Утро</b>"]
    if killed_by_mafia:
        role_line = ""
        if game["settings"].get("show_role_after_death"):
            target_role = _role(game, kill_target)
            role_label = ROLE_LABELS.get(target_role, "Неизвестно")
            role_line = f"\nРоль: <b>{role_label}</b>"
        lines.append(f"Ночью погиб {_mention(game['players'][kill_target])}.{role_line}")
    elif kill_target and kill_target == healed:
        lines.append("Доктор успел спасти жертву. Никто не погиб от рук мафии.")
    else:
        lines.append("Ночь прошла тихо. Никто не погиб от рук мафии.")

    if afk_removed:
        lines.append("")
        names = ", ".join(_mention(game["players"][uid]) for uid in afk_removed if uid in game["players"])
        lines.append(f"💤 Исключены за AFK этой ночью: {names}.")

    await _put_game_unlocked(chat_id, game)
    text = "\n".join(lines)

    await bot.send_message(chat_id, text, parse_mode="HTML")
    winner = _winner(game)
    if winner:
        await _end_game_internal(bot, chat_id, game, winner)
    else:
        await _start_discussion_internal(bot, chat_id, game)


async def _check_or_continue(bot, chat_id: int, game: dict[str, Any]) -> None:
    async with _get_chat_lock(chat_id):
        await _check_or_continue_internal(bot, chat_id, game)


async def _check_or_continue_internal(bot, chat_id: int, game: dict[str, Any]) -> None:
    winner = _winner(game)
    if winner:
        await _end_game_internal(bot, chat_id, game, winner)
    elif game.get("phase") == PHASE_NIGHT:
        if _night_ready(game):
            await _process_night_internal(bot, chat_id)
    else:
        await _start_discussion_internal(bot, chat_id, game)


def _winner(game: dict[str, Any]) -> str | None:
    alive = _alive_ids(game)
    mafia = [uid for uid in alive if _role(game, uid) == ROLE_MAFIA]
    civilians = [uid for uid in alive if _role(game, uid) != ROLE_MAFIA]
    if not mafia:
        return "Мирные"
    if len(mafia) >= len(civilians):
        return "Мафия"
    return None


async def _start_discussion(bot, chat_id: int, game: dict[str, Any]) -> None:
    async with _get_chat_lock(chat_id):
        await _start_discussion_internal(bot, chat_id, game)


async def _start_discussion_internal(bot, chat_id: int, game: dict[str, Any]) -> None:
    game["phase"] = PHASE_DISCUSSION
    game["phase_deadline"] = _now() + game["settings"]["discussion"]
    await _put_game_unlocked(chat_id, game)
    _schedule_timer(bot, chat_id, game["phase_deadline"], PHASE_DISCUSSION)
    await bot.send_message(
        chat_id,
        "💬 <b>Обсуждение</b>\n\n"
        "Говорите, спорьте, ищите нестыковки.\n"
        "Бот не подсказывает и не анализирует игроков.\n\n"
        f"Время: <b>{game['settings']['discussion']} сек</b>",
        parse_mode="HTML",
    )


async def _start_vote(bot, chat_id: int) -> None:
    async with _get_chat_lock(chat_id):
        await _start_vote_internal(bot, chat_id)


async def _start_vote_internal(bot, chat_id: int) -> None:
    game = await _get_game_unlocked(chat_id)
    if not game or game.get("phase") not in {PHASE_DISCUSSION, PHASE_VOTING}:
        return
    game["phase"] = PHASE_VOTING
    game["phase_deadline"] = _now() + game["settings"]["vote"]
    game["votes"] = {}
    game["vote_changes"] = {}
    await _put_game_unlocked(chat_id, game)
    _schedule_timer(bot, chat_id, game["phase_deadline"], PHASE_VOTING)
    await bot.send_message(
        chat_id,
        "🗳 <b>Голосование</b>\n\n"
        "Выберите игрока, которого хотите исключить.\n"
        f"Сменить голос можно <b>{game['settings']['vote_change_limit']}</b> раз.\n"
        "При ничьей никто не выбывает.\n\n"
        f"Время: <b>{game['settings']['vote']} сек</b>",
        reply_markup=_vote_keyboard(game),
        parse_mode="HTML",
    )


async def _record_vote(call: CallbackQuery, target_id: str | None) -> None:
    chat_id = call.message.chat.id
    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or game.get("phase") != PHASE_VOTING:
            await call.answer("Сейчас нет голосования.", show_alert=True)
            return

        uid = str(call.from_user.id)
        if not _is_alive(game, uid):
            await call.answer("Голосовать могут только живые игроки.", show_alert=True)
            return
        if target_id and target_id not in _alive_ids(game):
            await call.answer("Цель недоступна.", show_alert=True)
            return

        if uid in game["votes"]:
            changes = game["vote_changes"].get(uid, 0)
            if changes >= game["settings"]["vote_change_limit"]:
                await call.answer("Лимит смены голоса исчерпан.", show_alert=True)
                return
            game["vote_changes"][uid] = changes + 1

        game["votes"][uid] = target_id
        if target_id:
            game["players"][uid]["afk"] = 0

        await _put_game_unlocked(chat_id, game)
        await call.answer("Голос принят.")

        if len(game["votes"]) >= len(_alive_ids(game)):
            await _process_vote_internal(call.bot, chat_id)


async def _process_vote(bot, chat_id: int) -> None:
    async with _get_chat_lock(chat_id):
        await _process_vote_internal(bot, chat_id)


async def _process_vote_internal(bot, chat_id: int) -> None:
    _cancel_timer(chat_id)
    game = await _get_game_unlocked(chat_id)
    if not game or game.get("phase") != PHASE_VOTING:
        return

    afk_removed = []
    if game["settings"]["afk_enabled"]:
        for uid in _alive_ids(game):
            if uid not in game.get("votes", {}):
                game["players"][uid]["afk"] = game["players"][uid].get("afk", 0) + 1
        afk_removed = _exclude_afk(game)

    votes = [target for target in game.get("votes", {}).values() if target]
    eliminated = None
    if votes:
        counts = {uid: votes.count(uid) for uid in set(votes)}
        if counts:
            top_count = max(counts.values())
            leaders = [uid for uid, count in counts.items() if count == top_count]
            if len(leaders) == 1:
                eliminated = leaders[0]
                _kill_player(game, eliminated)

    await _put_game_unlocked(chat_id, game)

    lines = ["⚖️ <b>Итоги голосования</b>", ""]
    if votes and not game["settings"].get("anonymous_voting"):
        counts = {uid: votes.count(uid) for uid in set(votes)}
        for uid, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"{_mention(game['players'][uid])}: <b>{count}</b>")
        lines.append("")

    if eliminated:
        role_line = ""
        if game["settings"].get("show_role_after_death"):
            target_role = _role(game, eliminated)
            role_label = ROLE_LABELS.get(target_role, "Неизвестно")
            role_line = f" Роль: <b>{role_label}</b>."
        lines.append(f"Исключен: {_mention(game['players'][eliminated])}.{role_line}")
    else:
        lines.append("Ничья. Никто не исключается.")

    if afk_removed:
        names = ", ".join(_mention(game["players"][uid]) for uid in afk_removed if uid in game["players"])
        lines.append(f"AFK исключение: {names}.")

    await bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")

    if eliminated:
        await _start_last_word_internal(bot, chat_id, game, eliminated)
    else:
        await _check_or_continue_internal(bot, chat_id, game)


async def _start_last_word_internal(bot, chat_id: int, game: dict[str, Any], eliminated_uid: str) -> None:
    """Даёт исключённому 30 сек на последнее слово."""
    game["phase"] = PHASE_LAST_WORD
    game["last_word_uid"] = eliminated_uid
    game["last_word_deadline"] = _now() + 30
    await _put_game_unlocked(chat_id, game)
    player = game["players"].get(eliminated_uid)
    name = _mention(player) if player else "Игрок"
    await bot.send_message(
        chat_id,
        f"🎤 {name} исключён. <b>30 секунд на последнее слово.</b>\nНапишите сообщение боту в личные сообщения.",
        parse_mode="HTML",
    )
    if player:
        if player.get("is_bot"):
            await asyncio.sleep(1)
            async with _get_chat_lock(chat_id):
                game = await _get_game_unlocked(chat_id)
                if game and game.get("phase") == PHASE_LAST_WORD and game.get("last_word_uid") == eliminated_uid:
                    await _finish_last_word_internal(bot, chat_id, game)
            return
        try:
            await bot.send_message(
                int(eliminated_uid),
                "🎤 <b>Последнее слово</b>\n\nВас исключили. У вас 30 секунд — напишите что-нибудь, бот перешлёт в чат.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    # Через 30 сек автоматически продолжаем игру
    asyncio.create_task(_last_word_timeout(bot, chat_id, eliminated_uid, game["last_word_deadline"]))


async def _last_word_timeout(bot: Bot, chat_id: int, uid: str, deadline: int) -> None:
    try:
        await asyncio.sleep(max(0, deadline - _now()))
        async with _get_chat_lock(chat_id):
            game = await _get_game_unlocked(chat_id)
            if not game or game.get("phase") != PHASE_LAST_WORD or game.get("last_word_uid") != uid:
                return
            await _finish_last_word_internal(bot, chat_id, game)
    except asyncio.CancelledError:
        pass


async def _finish_last_word_internal(bot, chat_id: int, game: dict[str, Any]) -> None:
    game.pop("last_word_uid", None)
    game.pop("last_word_deadline", None)
    await _put_game_unlocked(chat_id, game)
    await _check_or_continue_internal(bot, chat_id, game)


async def _end_game(bot, chat_id: int, game: dict[str, Any], winner: str) -> None:
    async with _get_chat_lock(chat_id):
        await _end_game_internal(bot, chat_id, game, winner)


async def _end_game_internal(bot, chat_id: int, game: dict[str, Any], winner: str) -> None:
    _cancel_timer(chat_id)
    game["phase"] = PHASE_GAME_END
    await _put_game_unlocked(chat_id, game)
    roles = []
    for uid, role in game.get("roles", {}).items():
        player = game["players"].get(uid)
        if player:
            roles.append(f"{_mention(player)} — <b>{ROLE_LABELS[role]}</b>")

    await bot.send_message(
        chat_id,
        f"🏁 <b>Игра окончена</b>\n\n"
        f"Победили: <b>{winner}</b>\n"
        f"Ночей сыграно: <b>{game.get('night', 0)}</b>\n\n"
        "<b>Роли</b>\n" + "\n".join(roles) + "\n\n"
        "Новая партия: /mafia",
        parse_mode="HTML",
    )
    _record_stats(game, winner)
    await _delete_game_unlocked(chat_id, game.get("settings"))


async def _restore_night(bot: Bot, chat_id: int) -> None:
    async with _get_chat_lock(chat_id):
        await _process_night_internal(bot, chat_id)


@router.startup()
async def mafia_restore_timers(bot: Bot) -> None:
    data = await asyncio.to_thread(_load_all)
    for raw_chat_id, game in data.items():
        phase = game.get("phase")
        deadline = game.get("phase_deadline")
        if phase in {PHASE_LOBBY, PHASE_NIGHT, PHASE_DISCUSSION, PHASE_VOTING} and deadline:
            chat_id = int(raw_chat_id)
            if int(deadline) <= _now():
                if phase == PHASE_LOBBY:
                    await _delete_game(chat_id, game.get("settings"))
                    await bot.send_message(chat_id, "⌛ Лобби мафии закрыто после перезагрузки: игра не началась вовремя.")
                elif phase == PHASE_NIGHT:
                    asyncio.create_task(_restore_night(bot, chat_id))
                elif phase == PHASE_DISCUSSION:
                    asyncio.create_task(_start_vote(bot, chat_id))
                elif phase == PHASE_VOTING:
                    asyncio.create_task(_process_vote(bot, chat_id))
            else:
                _schedule_timer(bot, chat_id, int(deadline), phase)


@router.message(Command("mafia"))
async def cmd_mafia(message: Message):
    if message.chat.type == "private":
        await message.reply("Мафия запускается в группе.")
        return
    game = await _get_game(message.chat.id)
    if game and game.get("phase") not in {PHASE_IDLE, PHASE_GAME_END}:
        await _send_lobby(message, game)
        return
    settings = game.get("settings") if game else None
    game = _new_game(message.chat.id, message, settings=settings)
    await _put_game(message.chat.id, game)
    _schedule_timer(message.bot, message.chat.id, game["phase_deadline"], PHASE_LOBBY)
    await _send_lobby(message, game)


@router.message(Command("join"))
async def cmd_join(message: Message):
    await _join_player(message)


@router.message(Command("leave"))
async def cmd_leave(message: Message):
    await _leave_player(message)


@router.message(Command("ready"))
async def cmd_ready(message: Message):
    await _ready_player(message)


@router.message(Command("startmafia"))
async def cmd_startmafia(message: Message):
    await _start_game(message)


@router.message(Command("cancelmafia"))
async def cmd_cancelmafia(message: Message):
    chat_id, game = await _game_for_event(message)
    if not game:
        await message.reply("Сейчас нет активной игры. Создать: /mafia")
        return
    if not await _can_control(message.bot, game, message.from_user.id):
        await message.reply("Отменить игру может владелец или администратор.")
        return
    await _delete_game(chat_id, game.get("settings"))
    await message.reply("❌ Игра отменена.")


@router.message(Command("players"))
async def cmd_players(message: Message):
    game = await _require_game(message)
    if game:
        await message.reply(_format_lobby(game) if game["phase"] == PHASE_LOBBY else _format_status(game), parse_mode="HTML")


@router.message(Command("mstatus"))
async def cmd_status(message: Message):
    game = await _require_game(message)
    if game:
        await message.reply(_format_status(game), parse_mode="HTML")


@router.message(Command("role"))
async def cmd_role(message: Message):
    data = _load_all()
    for game in data.values():
        uid = str(message.from_user.id)
        if uid in game.get("players", {}) and game.get("roles", {}).get(uid):
            if game["settings"].get("resend_role", True):
                await message.reply(_role_text(game["roles"][uid]), parse_mode="HTML")
            else:
                await message.reply("Повторная отправка роли отключена настройками.")
            return
    await message.reply("У тебя нет роли в активной игре.")


@router.message(Command("helpmafia"))
async def cmd_helpmafia(message: Message):
    await message.reply(
        "📖 <b>Мафия в Chatrix</b>\n\n"
        "<b>Как начать</b>\n"
        "1. В группе напиши /mafia\n"
        "2. Игроки нажимают <b>Войти</b> и переключают <b>Готов / не готов</b>\n"
        "3. Владелец лобби нажимает <b>Начать игру</b>\n\n"
        "<b>Во время игры</b>\n"
        "/mstatus — статус партии\n"
        "/players — список игроков\n"
        "/role — напомнить свою роль\n"
        "/vote имя — проголосовать командой\n"
        "/skip — пропустить действие или голос\n\n"
        "<b>Ночные роли</b>\n"
        "/kill имя — ход мафии\n"
        "/heal имя — ход доктора\n"
        "/check имя — ход комиссара\n\n"
        "<b>Управление</b>\n"
        "/settings — настройки мафии\n"
        "/cancelmafia — отменить партию\n\n"
        "<b>Демо</b>\n"
        "/mafiademo — показать интерфейс без запуска игры\n\n"
        "Бот не подсказывает, не анализирует и не помогает игрокам искать мафию.",
        parse_mode="HTML",
    )


@router.message(Command("mafiatest"))
async def cmd_mafia_test(message: Message):
    game = _demo_game(message.chat.id, message.from_user.id, message.from_user.full_name)
    game["settings"] = dict(DEFAULT_SETTINGS)
    now = _now()
    game["players"] = {
        str(message.from_user.id): {"id": message.from_user.id, "name": message.from_user.full_name, "username": message.from_user.username, "is_bot": False, "joined_at": now, "ready": True, "afk": 0, "last_doctor_self_heal": False, "dm_ok": None},
        "900001": {"id": 900001, "name": "\u0422\u0435\u0441\u0442 \u0410\u043b\u0438\u0441\u0430", "username": None, "is_bot": True, "joined_at": now + 1, "ready": True, "afk": 0, "last_doctor_self_heal": False, "dm_ok": True},
        "900002": {"id": 900002, "name": "\u0422\u0435\u0441\u0442 \u0411\u043e\u0440\u0438\u0441", "username": None, "is_bot": True, "joined_at": now + 2, "ready": True, "afk": 0, "last_doctor_self_heal": False, "dm_ok": True},
        "900003": {"id": 900003, "name": "\u0422\u0435\u0441\u0442 \u041a\u0438\u0440\u0430", "username": None, "is_bot": True, "joined_at": now + 3, "ready": True, "afk": 0, "last_doctor_self_heal": False, "dm_ok": True},
    }
    await message.reply(
        "\U0001f9ea <b>\u0422\u0435\u0441\u0442\u043e\u0432\u043e\u0435 \u043b\u043e\u0431\u0431\u0438</b>\n\n\u042d\u0442\u043e \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440. \u0420\u0435\u0430\u043b\u044c\u043d\u0430\u044f \u0438\u0433\u0440\u0430 \u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u0435\u0442\u0441\u044f.",
        parse_mode="HTML",
    )
    await message.answer(
        _format_lobby(game),
        reply_markup=_demo_keyboard(["\u2795 \u0412\u043e\u0439\u0442\u0438", "\u2705 \u0413\u043e\u0442\u043e\u0432", "\U0001f510 \u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u041b\u0421", "\u25b6 \u041d\u0430\u0447\u0430\u0442\u044c \u0438\u0433\u0440\u0443", "\u26a1 \u041f\u0440\u0435\u0441\u0435\u0442\u044b"], width=2),
        parse_mode="HTML",
    )


@router.message(Command("mafiademo", "demomafia"))
async def cmd_mafia_demo(message: Message):
    game = _demo_game(message.chat.id, message.from_user.id, message.from_user.full_name)
    await message.reply(
        "🧪 <b>Демо мафии</b>\n\n"
        "Это только визуальный просмотр экранов. Настоящая игра не запускается, кнопки в демо ничего не меняют.",
        parse_mode="HTML",
    )
    await message.answer(
        _format_lobby(game),
        reply_markup=_demo_keyboard(["➕ Войти в игру", "✅ Готов / не готов", "▶ Начать игру", "👥 Игроки", "➖ Выйти", "❌ Закрыть лобби"]),
        parse_mode="HTML",
    )
    night_game = dict(game)
    night_game["phase"] = PHASE_NIGHT
    night_game["phase_deadline"] = _now() + 45
    await message.answer(
        f"🌙 <b>Ночь {night_game['night']}</b>\n\nГород засыпает. Активные роли получили действия в личные сообщения.\nНа ход есть <b>{night_game['settings']['night']} сек</b>.",
        parse_mode="HTML",
    )
    await message.answer(
        _night_action_text(night_game, ROLE_MAFIA, "Алиса"),
        reply_markup=_demo_keyboard(["CrazyTapok", "Борис", "Кира", "⏭ Пропустить действие"], width=1),
        parse_mode="HTML",
    )
    discussion_game = dict(game)
    discussion_game["phase"] = PHASE_DISCUSSION
    discussion_game["phase_deadline"] = _now() + 90
    await message.answer("☀️ <b>Утро</b>\n\nНочь прошла тихо. Никто не погиб.", parse_mode="HTML")
    await message.answer(
        f"💬 <b>Обсуждение</b>\n\nГоворите, спорьте, ищите нестыковки.\nБот не подсказывает и не анализирует игроков.\n\nВремя: <b>{discussion_game['settings']['discussion']} сек</b>",
        parse_mode="HTML",
    )
    vote_game = dict(game)
    vote_game["phase"] = PHASE_VOTING
    vote_game["phase_deadline"] = _now() + 30
    await message.answer(
        f"🗳 <b>Голосование</b>\n\nВыберите игрока, которого хотите исключить.\nСменить голос можно <b>{vote_game['settings']['vote_change_limit']}</b> раз.\nПри ничьей никто не выбывает.\n\nВремя: <b>{vote_game['settings']['vote']} сек</b>",
        reply_markup=_demo_keyboard(["CrazyTapok", "Алиса", "Борис", "Кира", "⏭ Воздержаться"], width=1),
        parse_mode="HTML",
    )
    await message.answer("⚖️ <b>Итоги голосования</b>\n\nАлиса: <b>2</b>\nБорис: <b>1</b>\n\nИсключен: Алиса.", parse_mode="HTML")
    await message.answer(
        "🏁 <b>Игра окончена</b>\n\nПобедили: <b>Мирные</b>\nНочей сыграно: <b>2</b>\n\n<b>Роли</b>\nCrazyTapok — <b>Мирный житель</b>\nАлиса — <b>Мафия</b>\nБорис — <b>Доктор</b>\nКира — <b>Комиссар</b>\n\nНовая партия: /mafia",
        parse_mode="HTML",
    )
    await message.answer(
        _settings_text(game),
        reply_markup=_demo_keyboard(["Минимум игроков: 4", "−", "+", "Время обсуждения: 90 сек.", "−", "+", "Исключать за AFK: Да", "Скрывать голоса: Нет", "♻ Сброс"], width=1),
        parse_mode="HTML",
    )


@router.message(Command("skip"))
async def cmd_skip(message: Message):
    chat_id, game = await _game_for_event(message)
    if not game:
        await message.reply("Сейчас нет активной игры. Создать: /mafia")
        return

    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game:
            return

        if game["phase"] == PHASE_DISCUSSION and await _can_control(message.bot, game, message.from_user.id):
            await _start_vote_internal(message.bot, chat_id)
            return

        if game["phase"] == PHASE_VOTING and _is_alive(game, message.from_user.id):
            game["votes"][str(message.from_user.id)] = None
            await _put_game_unlocked(chat_id, game)
            await message.reply("Пропуск голоса принят.")
            return

        if game["phase"] == PHASE_NIGHT and _is_alive(game, message.from_user.id):
            uid = str(message.from_user.id)
            if uid not in game.setdefault("skips", []):
                game["skips"].append(uid)
                await _put_game_unlocked(chat_id, game)
                await message.reply("Ночной пропуск принят.")
                if _night_ready(game):
                    await _process_night_internal(message.bot, chat_id)
            return

    await message.reply("Сейчас пропуск недоступен.")


@router.message(Command("vote"))
async def cmd_vote(message: Message):
    chat_id, _ = await _game_for_event(message)
    if chat_id is None:
        await message.reply("Сейчас нет активной игры. Создать: /mafia")
        return

    target_query = _command_args(message)

    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or game["phase"] != PHASE_VOTING:
            await message.reply("Сейчас нет голосования.")
            return

        if not target_query:
            await message.reply("Выбери игрока:", reply_markup=_vote_keyboard(game))
            return

        target_id = _find_target(game, target_query)
        if not target_id:
            await message.reply("Не нашел такого живого игрока. Можно выбрать кнопкой:", reply_markup=_vote_keyboard(game))
            return

        uid = str(message.from_user.id)
        if not _is_alive(game, uid):
            await message.reply("Голосовать могут только живые игроки.")
            return

        if uid in game["votes"]:
            changes = game["vote_changes"].get(uid, 0)
            if changes >= game["settings"]["vote_change_limit"]:
                await message.reply("Лимит смены голоса исчерпан.")
                return
            game["vote_changes"][uid] = changes + 1

        game["votes"][uid] = target_id
        game["players"][uid]["afk"] = 0
        await _put_game_unlocked(chat_id, game)
        await message.reply("Голос принят.")

        if len(game["votes"]) >= len(_alive_ids(game)):
            await _process_vote_internal(message.bot, chat_id)


@router.message(Command("kill", "heal", "check"))
async def cmd_night_action(message: Message):
    if message.chat.type != "private":
        await message.reply("Ночные действия принимаются только в личных сообщениях с ботом.")
        return

    chat_id, _ = await _game_for_event(message)
    if chat_id is None:
        await message.reply("Активная игра не найдена.")
        return

    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or game["phase"] != PHASE_NIGHT:
            await message.reply("Сейчас не ночь или ты не участвуешь в активной игре.")
            return

        command = message.text.split()[0].lstrip("/").split("@")[0].lower()
        action = {"kill": "kill", "heal": "heal", "check": "check"}[command]
        target_query = _command_args(message)

        if not target_query:
            await message.reply("Выбери цель:", reply_markup=_target_keyboard(game, action, message.from_user.id))
            return

        target_id = _find_target(game, target_query)
        if not target_id:
            await message.reply("Не нашел такого живого игрока. Можно выбрать кнопкой:", reply_markup=_target_keyboard(game, action, message.from_user.id))
            return

        uid = str(message.from_user.id)
        role = _role(game, uid)

        if action == "kill" and role != ROLE_MAFIA:
            await message.reply("Это действие доступно только мафии.")
            return
        if action == "heal" and role != ROLE_DOCTOR:
            await message.reply("Это действие доступно только доктору.")
            return
        if action == "check" and role != ROLE_COMMISSAR:
            await message.reply("Это действие доступно только комиссару.")
            return
        if action == "heal" and target_id == uid and not game["settings"]["doctor_self_heal"]:
            await message.reply("Самолечение отключено настройками.")
            return
        if action == "heal" and target_id == uid and game["players"][uid].get("last_doctor_self_heal"):
            await message.reply("Нельзя лечить себя два раза подряд.")
            return

        if action == "kill":
            game["night_actions"]["mafia"][uid] = target_id
        elif action == "heal":
            game["night_actions"]["doctor"] = target_id
        elif action == "check":
            game["night_actions"]["commissar"] = target_id
            result = "МАФИЯ" if _role(game, target_id) == ROLE_MAFIA else "НЕ МАФИЯ"
            await message.reply(f"Проверка: <b>{escape(game['players'][target_id]['name'])}</b> — <b>{result}</b>", parse_mode="HTML")

        await _put_game_unlocked(chat_id, game)

        if action != "check":
            await message.reply("Действие принято.")

        if _night_ready(game):
            await _process_night_internal(message.bot, chat_id)


@router.message(Command("settings"))
async def cmd_mafia_settings(message: Message):
    game = await _get_game(message.chat.id)
    if not game:
        # FIX: owner берём из message, не из game
        game = {
            "chat_id": message.chat.id,
            "owner": message.from_user.id,
            "phase": PHASE_IDLE,
            "settings": dict(DEFAULT_SETTINGS),
            "players": {},
        }
        await _put_game(message.chat.id, game)
    if not await _can_control(message.bot, game, message.from_user.id):
        await message.reply("Настройки мафии доступны владельцу игры или администратору.")
        return
    await message.reply(_settings_text(game), reply_markup=_settings_keyboard(game), parse_mode="HTML")


@router.message(Command("resetsettings"))
async def cmd_resetsettings(message: Message):
    game = await _get_game(message.chat.id)
    if not game:
        game = {
            "chat_id": message.chat.id,
            "owner": message.from_user.id,
            "phase": PHASE_IDLE,
            "settings": dict(DEFAULT_SETTINGS),
            "players": {},
        }
    if not await _can_control(message.bot, game, message.from_user.id):
        await message.reply("Сброс доступен владельцу игры или администратору.")
        return
    game["settings"] = dict(DEFAULT_SETTINGS)
    await _put_game(message.chat.id, game)
    await message.reply("♻ Настройки мафии сброшены.")


@router.callback_query(F.data == "maf:join")
async def cb_join(call: CallbackQuery):
    await _join_player(call)
    await call.answer()


@router.callback_query(F.data == "maf:leave")
async def cb_leave(call: CallbackQuery):
    await _leave_player(call)
    await call.answer()


@router.callback_query(F.data == "maf:ready")
async def cb_ready(call: CallbackQuery):
    await _ready_player(call)
    await call.answer()


@router.callback_query(F.data == "maf:checkdm")
async def cb_checkdm(call: CallbackQuery):
    game = await _get_game(call.message.chat.id)
    if not game or game.get("phase") != PHASE_LOBBY:
        await call.answer("\u041b\u043e\u0431\u0431\u0438 \u043d\u0435\u0442.", show_alert=True)
        return
    uid = str(call.from_user.id)
    player = game.get("players", {}).get(uid)
    if not player:
        await call.answer("\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u043e\u0439\u0434\u0438 \u0432 \u0438\u0433\u0440\u0443.", show_alert=True)
        return
    ok = await _check_player_dm(call.bot, player, notify=True)
    await _put_game(call.message.chat.id, game)
    await _send_lobby(call, game)
    await call.answer("\u041b\u0421 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442." if ok else "\u041e\u0442\u043a\u0440\u043e\u0439 \u0431\u043e\u0442\u0430 \u0432 \u041b\u0421 \u0438 \u043d\u0430\u0436\u043c\u0438 Start.", show_alert=not ok)


@router.callback_query(F.data == "maf:start")
async def cb_start(call: CallbackQuery):
    await _start_game(call)
    await call.answer()


@router.callback_query(F.data == "maf:cancel")
async def cb_cancel(call: CallbackQuery):
    game = await _get_game(call.message.chat.id)
    if not game:
        await call.answer("Игры нет.", show_alert=True)
        return
    if not await _can_control(call.bot, game, call.from_user.id):
        await call.answer("Только владелец или администратор.", show_alert=True)
        return
    await _delete_game(call.message.chat.id, game.get("settings"))
    await call.message.edit_text("❌ Игра отменена.")
    await call.answer()


@router.callback_query(F.data == "maf:players")
async def cb_players(call: CallbackQuery):
    game = await _get_game(call.message.chat.id)
    if game:
        await call.message.answer(_format_lobby(game) if game["phase"] == PHASE_LOBBY else _format_status(game), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("maf:kill:"))
async def cb_kill(call: CallbackQuery):
    await _record_night_action(call, "kill", call.data.split(":")[-1])


@router.callback_query(F.data.startswith("maf:heal:"))
async def cb_heal(call: CallbackQuery):
    await _record_night_action(call, "heal", call.data.split(":")[-1])


@router.callback_query(F.data.startswith("maf:check:"))
async def cb_check(call: CallbackQuery):
    await _record_night_action(call, "check", call.data.split(":")[-1])


@router.callback_query(F.data.startswith("maf:skip:"))
async def cb_night_skip(call: CallbackQuery):
    await _record_night_action(call, "skip", None)


@router.callback_query(F.data.startswith("maf:vote:"))
async def cb_vote(call: CallbackQuery):
    target = call.data.split(":")[-1]
    await _record_vote(call, None if target == "skip" else target)


@router.callback_query(F.data.startswith("maf:set:"))
async def cb_setting(call: CallbackQuery):
    chat_id = call.message.chat.id
    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or not await _can_control(call.bot, game, call.from_user.id):
            await call.answer("Недоступно.", show_alert=True)
            return
        _, _, key, direction = call.data.split(":")
        label, _short_label, min_value, max_value, step = SETTING_META[key]
        value = game["settings"][key] + (step if direction == "+" else -step)
        game["settings"][key] = max(min_value, min(max_value, value))
        if game["settings"]["min_players"] > game["settings"]["max_players"]:
            if direction == "+":
                game["settings"]["max_players"] = game["settings"]["min_players"]
            else:
                game["settings"]["min_players"] = game["settings"]["max_players"]
        await _put_game_unlocked(chat_id, game)
        await call.message.edit_text(_settings_text(game), reply_markup=_settings_keyboard(game), parse_mode="HTML")
        await call.answer(f"{label}: {game['settings'][key]}")


@router.callback_query(F.data.startswith("maf:toggle:"))
async def cb_toggle(call: CallbackQuery):
    chat_id = call.message.chat.id
    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or not await _can_control(call.bot, game, call.from_user.id):
            await call.answer("Недоступно.", show_alert=True)
            return
        key = call.data.split(":")[-1]
        game["settings"][key] = not game["settings"][key]
        await _put_game_unlocked(chat_id, game)
        await call.message.edit_text(_settings_text(game), reply_markup=_settings_keyboard(game), parse_mode="HTML")
        await call.answer("Сохранено.")


@router.callback_query(F.data.startswith("maf:preset:"))
async def cb_preset(call: CallbackQuery):
    chat_id = call.message.chat.id
    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or not await _can_control(call.bot, game, call.from_user.id):
            await call.answer("\u041d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e.", show_alert=True)
            return
        preset_id = call.data.split(":")[-1]
        preset = MAFIA_PRESETS.get(preset_id)
        if not preset:
            await call.answer("\u041f\u0440\u0435\u0441\u0435\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", show_alert=True)
            return
        label, values = preset
        _ensure_settings(game).update(values)
        await _put_game_unlocked(chat_id, game)
        await call.message.edit_text(_settings_text(game), reply_markup=_settings_keyboard(game), parse_mode="HTML")
        await call.answer(f"\u041f\u0440\u0435\u0441\u0435\u0442: {label}")


@router.callback_query(F.data == "maf:resetsettings")
async def cb_resetsettings(call: CallbackQuery):
    chat_id = call.message.chat.id
    async with _get_chat_lock(chat_id):
        game = await _get_game_unlocked(chat_id)
        if not game or not await _can_control(call.bot, game, call.from_user.id):
            await call.answer("Недоступно.", show_alert=True)
            return
        game["settings"] = dict(DEFAULT_SETTINGS)
        await _put_game_unlocked(chat_id, game)
        await call.message.edit_text(_settings_text(game), reply_markup=_settings_keyboard(game), parse_mode="HTML")
        await call.answer("Настройки сброшены.")




@router.message(Command("mafiastats"))
async def cmd_mafia_stats(message: Message):
    data = _load_stats()
    if not data:
        await message.reply("Статистики пока нет. Сыграйте хотя бы одну партию!")
        return
    lines = ["📊 <b>Статистика мафии</b>\n"]
    # Сортируем по суммарным победам
    players = sorted(data.items(), key=lambda x: sum(r.get("wins", 0) for r in x[1]["roles"].values()), reverse=True)
    for uid, info in players[:15]:
        name = escape(info.get("name", "Игрок"))
        role_lines = []
        for role, stats in info["roles"].items():
            label = ROLE_LABELS.get(role, role)
            w, l = stats.get("wins", 0), stats.get("losses", 0)
            total = w + l
            pct = int(w / total * 100) if total else 0
            role_lines.append(f"  {label}: {w}п/{l}п ({pct}%)")
        lines.append(f"<b>{name}</b>\n" + "\n".join(role_lines))
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "maf:noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


async def _is_player_in_active_game(message: Message) -> bool:
    """Фильтр: пользователь находится в активной игре (не в лобби и не завершенной)."""
    return await _find_user_game(message.from_user.id) is not None

# ─── Чат мафии через ЛС ───────────────────────────────────────────────────────

@router.message(F.chat.type == "private", F.text, _is_player_in_active_game)
async def mafia_private_chat(message: Message):
    """Ночью — чат мафии. Фаза последнего слова — пересылка в группу."""
    chat_id = await _find_user_game(message.from_user.id)
    if not chat_id:
        return
    game = await _get_game(chat_id)
    if not game:
        return
    uid = str(message.from_user.id)

    # Последнее слово
    if game.get("phase") == PHASE_LAST_WORD and game.get("last_word_uid") == uid:
        sender = escape(game["players"][uid].get("name") or "Игрок")
        await message.bot.send_message(
            chat_id,
            f"🎤 <b>{sender}:</b> {escape(message.text)}",
            parse_mode="HTML",
        )
        await message.reply("✉️ Сообщение отправлено в чат.")
        async with _get_chat_lock(chat_id):
            game = await _get_game_unlocked(chat_id)
            if game and game.get("phase") == PHASE_LAST_WORD and game.get("last_word_uid") == uid:
                await _finish_last_word_internal(message.bot, chat_id, game)
        return

    # Чат мафии ночью
    if game.get("phase") != PHASE_NIGHT:
        return
    if _role(game, uid) != ROLE_MAFIA or not _is_alive(game, uid):
        return
    mafia_ids = [u for u in _alive_ids(game) if _role(game, u) == ROLE_MAFIA and u != uid]
    if not mafia_ids:
        await message.reply("Ты единственный в мафии.")
        return
    sender = escape(game["players"][uid].get("name") or "Мафиози")
    text = f"🎭 <b>{sender}:</b> {escape(message.text)}"
    for mid in mafia_ids:
        try:
            await message.bot.send_message(int(mid), text, parse_mode="HTML")
        except Exception:
            pass
    await message.reply("✉️ Отправлено союзникам.")