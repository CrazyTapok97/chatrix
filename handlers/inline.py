import hashlib
import logging
import secrets
from collections import OrderedDict

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ChosenInlineResult,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputMediaPhoto,
    InputTextMessageContent,
)

from config import MEME_CACHE_CHAT_ID
from utils.meme_gen import create_classic_meme
from utils.meme_storage import get_meme_by_id, get_random_memes, index_memes

logger = logging.getLogger(__name__)

router = Router()
_pending_memes: OrderedDict[str, tuple[int, str]] = OrderedDict()
_PENDING_LIMIT = 5000


def _remember_meme(result_id: str, meme_id: int, text: str) -> None:
    _pending_memes[result_id] = (meme_id, text)
    _pending_memes.move_to_end(result_id)
    while len(_pending_memes) > _PENDING_LIMIT:
        _pending_memes.popitem(last=False)


def _working_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏳ Создаю мем...", callback_data="meme:working")
    ]])

@router.inline_query()
async def inline_handler(query: InlineQuery):
    text = query.query.strip() or " "
    
    limit = 20
    
    try:
        if not query.offset:
            await index_memes()
        if query.offset:
            try:
                seed_text, offset_text = query.offset.split(":", maxsplit=1)
                seed = int(seed_text)
                offset = int(offset_text)
            except (TypeError, ValueError):
                seed = secrets.randbelow(2_147_483_646) + 1
                offset = 0
        else:
            seed = secrets.randbelow(2_147_483_646) + 1
            offset = 0

        memes = get_random_memes(limit=limit, offset=offset, seed=seed)
        results = []
        
        for meme_id, file_path, file_id, thumb_id in memes:
            text_hash = hashlib.sha256(
                f"{query.from_user.id}:{text}".encode()
            ).hexdigest()[:20]
            result_id = f"meme_{meme_id}_{text_hash}"
            _remember_meme(result_id, meme_id, text)
            
            if file_id:
                results.append(InlineQueryResultCachedPhoto(
                    id=result_id,
                    photo_file_id=file_id,
                    title=f"Мем #{meme_id}",
                    description="Выбрать шаблон и создать мем",
                    caption="⏳ Создаю мем...",
                    reply_markup=_working_keyboard(),
                ))
            else:
                results.append(InlineQueryResultArticle(
                    id=result_id,
                    title=f"Мем #{meme_id} (индексация)",
                    description="Нажми, чтобы выбрать этот шаблон. Рекомендуется выполнить 'S index'.",
                    input_message_content=InputTextMessageContent(message_text=f"Индексация нужна для #{meme_id}")
                ))

        next_offset = f"{seed}:{offset + len(memes)}" if len(memes) == limit else ""
        logger.info(
            "Inline gallery: user=%s offset=%s results=%s next_offset=%s",
            query.from_user.id,
            query.offset or "first",
            len(results),
            next_offset or "end",
        )
        await query.answer(
            results,
            cache_time=0,
            is_personal=True,
            next_offset=next_offset,
        )
    except Exception as e:
        logger.exception(f"Error in inline_handler: {e}")
        await query.answer([], cache_time=1)

@router.chosen_inline_result()
async def chosen_meme_handler(chosen_result: ChosenInlineResult):
    """Заменяет выбранный inline-шаблон готовым мемом в том же сообщении."""
    logger.info(f"Chosen result received. result_id: {chosen_result.result_id}")
    pending = _pending_memes.get(chosen_result.result_id)
    if not pending:
        logger.error(f"Pending meme data not found: {chosen_result.result_id}")
        return
    if not chosen_result.inline_message_id:
        logger.error("inline_message_id is missing; inline feedback may be disabled")
        return

    meme_id, text = pending
    meme = get_meme_by_id(meme_id)
    if not meme:
        logger.error(f"Meme #{meme_id} not found")
        return

    _, file_path, _, _ = meme
    cache_message = None
    try:
        meme_bytes = create_classic_meme(file_path, text)
        cache_message = await chosen_result.bot.send_photo(
            chat_id=MEME_CACHE_CHAT_ID,
            photo=BufferedInputFile(meme_bytes, filename="meme.jpg"),
        )
        generated_file_id = cache_message.photo[-1].file_id

        await chosen_result.bot.edit_message_media(
            inline_message_id=chosen_result.inline_message_id,
            media=InputMediaPhoto(media=generated_file_id),
        )
        logger.info(f"Inline meme #{meme_id} generated and replaced")
    except Exception as e:
        logger.error(f"Error replacing inline meme #{meme_id}: {e}")
        try:
            await chosen_result.bot.edit_message_caption(
                inline_message_id=chosen_result.inline_message_id,
                caption="❌ Не удалось создать мем.",
                reply_markup=None,
            )
        except Exception:
            pass
    finally:
        _pending_memes.pop(chosen_result.result_id, None)
        if cache_message:
            try:
                await cache_message.delete()
            except Exception as e:
                logger.warning(f"Could not delete cached meme message: {e}")


@router.callback_query(F.data == "meme:working")
async def meme_working_callback(call: CallbackQuery):
    await call.answer("Мем создается...")
