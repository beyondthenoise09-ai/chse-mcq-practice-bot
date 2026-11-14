"""Gateway implementation for real Telegram using aiogram 3 (needs aiogram >= 3.25 for coloured buttons)."""
from __future__ import annotations
import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import BufferedInputFile, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from .gateway import Gateway, PremiumFailed

log = logging.getLogger("botnex.tg")
_PREMIUM_HINTS = ("emoji", "entit", "icon", "premium", "document_invalid", "custom")

def to_markup(kb) -> InlineKeyboardMarkup | None:
    if not kb:
        return None
    rows = []
    for row in kb:
        out = []
        for b in row:
            kw = {"text": b.text}
            if b.url:
                kw["url"] = b.url
            else:
                kw["callback_data"] = b.data or "x:0"
            if b.style:
                kw["style"] = b.style                      # Bot API 9.4: primary / success / danger
            if b.icon_id:
                kw["icon_custom_emoji_id"] = b.icon_id     # premium mode only
            out.append(InlineKeyboardButton(**kw))
        rows.append(out)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def premium_used(text: str, kb) -> bool:
    if "<tg-emoji" in (text or ""):
        return True
    return any(b.icon_id for row in (kb or []) for b in row)

def _raise_if_premium(e: Exception, used: bool) -> None:
    if used and any(h in str(e).lower() for h in _PREMIUM_HINTS):
        raise PremiumFailed(str(e)) from e

class AiogramGateway(Gateway):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def _call(self, coro_fn, retries: int = 2):
        for attempt in range(retries + 1):
            try:
                return await coro_fn()
            except TelegramRetryAfter as e:
                if attempt == retries:
                    raise
                await asyncio.sleep(float(e.retry_after) + 0.5)

    async def send_text(self, chat_id, text, kb=None):
        used = premium_used(text, kb)
        try:
            m = await self._call(lambda: self.bot.send_message(chat_id, text, reply_markup=to_markup(kb)))
        except TelegramBadRequest as e:
            _raise_if_premium(e, used)
            raise
        return m.message_id

    async def edit_text(self, chat_id, mid, text, kb=None, is_media=False):
        used = premium_used(text, kb)
        try:
            if is_media:
                await self._call(lambda: self.bot.edit_message_caption(
                    chat_id=chat_id, message_id=mid, caption=text, reply_markup=to_markup(kb)))
            else:
                await self._call(lambda: self.bot.edit_message_text(
                    text, chat_id=chat_id, message_id=mid, reply_markup=to_markup(kb)))
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            _raise_if_premium(e, used)
            raise

    async def edit_kb(self, chat_id, mid, kb):
        try:
            await self._call(lambda: self.bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=mid, reply_markup=to_markup(kb)))
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            raise

    async def delete(self, chat_id, mid):
        try:
            await self.bot.delete_message(chat_id, mid)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass

    async def send_sticker(self, chat_id, file_id):
        try:
            await self._call(lambda: self.bot.send_sticker(chat_id, file_id))
            return True
        except TelegramBadRequest as e:
            log.warning("send_sticker rejected: %s", e)
            return False

    async def send_welcome(self, chat_id, caption, kb, kind, file_id, asset_path):
        used = premium_used(caption, kb)
        markup = to_markup(kb)
        if file_id:                                           # cached / owner-set media
            try:
                if kind == "photo":
                    m = await self._call(lambda: self.bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup))
                    return "photo", m.photo[-1].file_id
                m = await self._call(lambda: self.bot.send_animation(chat_id, file_id, caption=caption, reply_markup=markup))
                return "animation", m.animation.file_id
            except TelegramBadRequest as e:
                _raise_if_premium(e, used)
                log.warning("Stored welcome media rejected, using default asset: %s", e)
        if asset_path:
            try:
                f = FSInputFile(asset_path)
                if asset_path.endswith(".mp4"):
                    m = await self._call(lambda: self.bot.send_animation(chat_id, f, caption=caption, reply_markup=markup))
                    return "animation", m.animation.file_id
                m = await self._call(lambda: self.bot.send_photo(chat_id, f, caption=caption, reply_markup=markup))
                return "photo", m.photo[-1].file_id
            except TelegramBadRequest as e:
                _raise_if_premium(e, used)
                log.error("Welcome asset failed, sending text only: %s", e)
        await self.send_text(chat_id, caption, kb)
        return "", ""

    async def send_photo_bytes(self, chat_id, data, caption, kb=None):
        used = premium_used(caption, kb)
        try:
            m = await self._call(lambda: self.bot.send_photo(
                chat_id, BufferedInputFile(data, "BOTNEX_Certificate.png"), caption=caption, reply_markup=to_markup(kb)))
        except TelegramBadRequest as e:
            _raise_if_premium(e, used)
            raise
        return m.photo[-1].file_id

    async def send_document_bytes(self, chat_id, data, filename, caption):
        m = await self._call(lambda: self.bot.send_document(chat_id, BufferedInputFile(data, filename), caption=caption))
        return m.document.file_id

    async def answer_cb(self, cb_id, text="", alert=False):
        try:
            await self.bot.answer_callback_query(cb_id, text=text or None, show_alert=alert)
        except (TelegramBadRequest, TelegramForbiddenError) as e:   # query too old / already answered
            log.debug("answer_cb ignored: %s", e)
