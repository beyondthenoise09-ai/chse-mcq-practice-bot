"""aiogram wiring: turns Telegram updates into Ctx/Incoming and hands them to the Controller."""
from __future__ import annotations
import logging
from aiogram import Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from .gateway import Ctx, Incoming

log = logging.getLogger("botnex.app")

def ctx_from_message(m: Message) -> Ctx:
    u = m.from_user
    return Ctx(user_id=u.id, first_name=u.first_name or "", username=u.username or "", chat_id=m.chat.id,
               message_id=m.message_id)

def ctx_from_callback(q: CallbackQuery) -> Ctx | None:
    msg = q.message
    if not isinstance(msg, Message):                          # inaccessible / inline message
        return None
    u = q.from_user
    is_media = bool(msg.photo or msg.animation or msg.video or msg.document or msg.sticker)
    return Ctx(user_id=u.id, first_name=u.first_name or "", username=u.username or "", chat_id=msg.chat.id,
               message_id=msg.message_id, is_media=is_media, cb_id=q.id, data=q.data or "")

def incoming_from(m: Message) -> Incoming:
    ents = list(m.entities or []) + list(m.caption_entities or [])
    emoji_ids = [e.custom_emoji_id for e in ents if getattr(e, "type", "") == "custom_emoji" and e.custom_emoji_id]
    if m.sticker:
        return Incoming("sticker", m.sticker.file_id, m.text or "", emoji_ids)
    if m.animation:
        return Incoming("animation", m.animation.file_id, m.caption or "", emoji_ids)
    if m.photo:
        return Incoming("photo", m.photo[-1].file_id, m.caption or "", emoji_ids)
    if m.text:
        return Incoming("text", "", m.text, emoji_ids)
    return Incoming("other", "", m.caption or "", emoji_ids)

def build_dispatcher(ctrl) -> Dispatcher:
    dp = Dispatcher()
    r = Router()

    @r.message(CommandStart(), F.chat.type == "private")
    async def on_start(m: Message):
        if m.from_user is None:
            return
        try:
            await ctrl.on_start(ctx_from_message(m))
        except Exception:
            log.exception("/start failed")

    @r.callback_query()
    async def on_cb(q: CallbackQuery):
        ctx = ctx_from_callback(q)
        if ctx is None:
            await q.answer("This button has expired. Send /start", show_alert=True)
            return
        try:
            await ctrl.on_callback(ctx)
        except Exception:
            log.exception("callback failed")
            try:
                await q.answer()
            except Exception:
                pass

    @r.message(F.chat.type == "private")
    async def on_other(m: Message):
        if m.from_user is None:
            return
        try:
            await ctrl.on_message(ctx_from_message(m), incoming_from(m))
        except Exception:
            log.exception("message handler failed")

    dp.include_router(r)
    return dp
