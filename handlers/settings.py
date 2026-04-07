"""
Хэндлер настроек: команда S c
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils.settings_store import get_access, set_access
from utils.access import is_admin

router = Router()


def _settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Параметры", callback_data="settings_params")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="settings_close")],
    ])


def _access_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="access_all")],
        [InlineKeyboardButton(text="👑 Только администраторы", callback_data="access_admin")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")],
    ])


def _params_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Команды (доступ)", callback_data="settings_access")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")],
    ])


# ─── Команда S c ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Cc]$"))
async def cmd_settings(message: Message):
    if not await is_admin(message) and message.chat.type != "private":
        await message.reply("⚠️ Настройки доступны только администраторам.")
        return
    await message.reply(
        "⚙️ <b>Настройки Сглыпы</b>\n\nВыберите раздел:",
        reply_markup=_settings_kb(),
        parse_mode="HTML",
    )


# ─── Колбэки ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_params")
async def cb_params(call: CallbackQuery):
    await call.message.edit_text(
        "⚙️ <b>Параметры</b>\n\nВыберите что настроить:",
        reply_markup=_params_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "settings_access")
async def cb_access_menu(call: CallbackQuery):
    current = await get_access(call.message.chat.id)
    label = "👥 Все" if current == "all" else "👑 Только админы"
    await call.message.edit_text(
        f"🔑 <b>Доступ к командам</b>\n\nТекущий режим: <b>{label}</b>\n\nВыберите новый режим:",
        reply_markup=_access_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.in_({"access_all", "access_admin"}))
async def cb_set_access(call: CallbackQuery):
    if not await is_admin(call.message):
        await call.answer("⚠️ Только для администраторов", show_alert=True)
        return
    mode = "all" if call.data == "access_all" else "admin"
    await set_access(call.message.chat.id, mode)
    label = "👥 Все пользователи" if mode == "all" else "👑 Только администраторы"
    await call.message.edit_text(
        f"✅ Доступ к командам изменён: <b>{label}</b>",
        parse_mode="HTML",
    )
    await call.answer("Сохранено!")


@router.callback_query(F.data == "settings_back")
async def cb_back(call: CallbackQuery):
    await call.message.edit_text(
        "⚙️ <b>Настройки Сглыпы</b>\n\nВыберите раздел:",
        reply_markup=_settings_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "settings_close")
async def cb_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()
