"""
Хэндлер настроек: команда S c
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils.settings_store import get_access, set_access, get_laziness, set_laziness, get_intelligence, set_intelligence
from utils.access import is_admin

router = Router()


def _settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Параметры", callback_data="settings_params")],
        [InlineKeyboardButton(text="🧠 Интеллект", callback_data="settings_intel")],
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
        [InlineKeyboardButton(text="💪 Лень (активность)", callback_data="settings_laziness")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")],
    ])


def _laziness_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ 0% (Макс. активный)", callback_data="laziness_0")],
        [InlineKeyboardButton(text="🐸 10% (Очень активный)", callback_data="laziness_10")],
        [InlineKeyboardButton(text="😐 50% (Средне)", callback_data="laziness_50")],
        [InlineKeyboardButton(text="💤 80% (Ленивый)", callback_data="laziness_80")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")],
    ])


def _intel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Классический (цитаты)", callback_data="intel_classic")],
        [InlineKeyboardButton(text="🚀 Максимальный", callback_data="intel_max")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")],
    ])


# ─── Команда S c ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^[Ss]\s+[Cc]$"))
@router.business_message(F.text.regexp(r"(?i)^[Ss]\s+[Cc]$"))
async def cmd_settings(message: Message):
    if not await is_admin(message) and message.chat.type != "private":
        await message.bot.send_message(
            chat_id=message.chat.id,
            text="⚠️ Настройки доступны только администраторам.",
            reply_to_message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
        return
    await message.bot.send_message(
        chat_id=message.chat.id,
        text="⚙️ <b>Настройки Чатрикса</b>\n\nВыберите раздел:",
        reply_markup=_settings_kb(),
        parse_mode="HTML",
        business_connection_id=message.business_connection_id
    )


# ─── Колбэки ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_params")
async def cb_params(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⚙️ <b>Параметры</b>\n\nВыберите что настроить:",
        reply_markup=_params_kb(),
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer()


@router.callback_query(F.data == "settings_access")
async def cb_access_menu(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    current = await get_access(call.message.chat.id)
    label = "👥 Все" if current == "all" else "👑 Только админы"
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔑 <b>Доступ к командам</b>\n\nТекущий режим: <b>{label}</b>\n\nВыберите новый режим:",
        reply_markup=_access_kb(),
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer()


@router.callback_query(F.data.in_({"access_all", "access_admin"}))
async def cb_set_access(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    if not await is_admin(call.message):
        await call.answer("⚠️ Только для администраторов", show_alert=True)
        return
    mode = "all" if call.data == "access_all" else "admin"
    await set_access(call.message.chat.id, mode)
    label = "👥 Все пользователи" if mode == "all" else "👑 Только администраторы"
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Доступ к командам изменён: <b>{label}</b>",
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer("Сохранено!")


@router.callback_query(F.data == "settings_laziness")
async def cb_laziness_menu(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    current = await get_laziness(call.message.chat.id)
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"💪 <b>Настройка лени</b>\n\n"
        f"Чем ниже процент, тем чаще Чатрикс будет сам вступать в диалог.\n\n"
        f"Текущая лень: <b>{current}%</b>",
        reply_markup=_laziness_kb(),
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer()


@router.callback_query(F.data == "settings_intel")
async def cb_intel_menu(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    current = await get_intelligence(call.message.chat.id)
    label = "🚀 Максимальный" if current == "max" else "📝 Классический"
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🧠 <b>Режим интеллекта</b>\n\n"
        f"<b>Классический:</b> Бот использует только фразы из истории чата.\n"
        f"<b>Максимальный:</b> Бот ведет осмысленные диалоги, используя контекст.\n\n"
        f"Текущий режим: <b>{label}</b>",
        reply_markup=_intel_kb(),
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer()


@router.callback_query(F.data.startswith("intel_"))
async def cb_set_intel(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    if not await is_admin(call.message):
        await call.answer("⚠️ Только для администраторов", show_alert=True)
        return
    mode = call.data.split("_")[1]
    await set_intelligence(call.message.chat.id, mode)
    label = "🚀 Максимальный" if mode == "max" else "📝 Классический (цитаты)"
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Интеллект Чатрикса установлен на: <b>{label}</b>",
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer("Сохранено!")


@router.callback_query(F.data.startswith("laziness_"))
async def cb_set_laziness(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    if not await is_admin(call.message):
        await call.answer("⚠️ Только для администраторов", show_alert=True)
        return
    value = int(call.data.split("_")[1])
    await set_laziness(call.message.chat.id, value)
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Лень Чатрикса установлена на <b>{value}%</b>",
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer("Сохранено!")


@router.callback_query(F.data == "settings_back")
async def cb_back(call: CallbackQuery):
    biz_id = call.message.business_connection_id
    await call.message.bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⚙️ <b>Настройки Чатрикса</b>\n\nВыберите раздел:",
        reply_markup=_settings_kb(),
        parse_mode="HTML",
        business_connection_id=biz_id
    )
    await call.answer()


@router.callback_query(F.data == "settings_close")
async def cb_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()
