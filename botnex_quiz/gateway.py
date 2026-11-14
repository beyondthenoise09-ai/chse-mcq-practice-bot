"""Telegram-independent types + the Gateway interface the bot logic talks to.

The quiz logic (flow.py) never imports aiogram; aio_gateway.py implements this interface
for real Telegram, tests use a fake. That keeps every user journey testable offline.
"""
from __future__ import annotations
from dataclasses import dataclass, field

class PremiumFailed(Exception):
    """Telegram rejected premium-only content (custom emoji / button icon)."""

@dataclass
class Btn:
    text: str
    data: str | None = None          # callback data (<=64 bytes)
    url: str | None = None
    style: str | None = None         # primary (blue) | success (green) | danger (red)
    icon_id: str | None = None       # custom emoji id (premium mode only)

Kb = list   # list[list[Btn]]

@dataclass
class Ctx:
    user_id: int
    first_name: str
    username: str
    chat_id: int
    message_id: int = 0
    is_media: bool = False
    cb_id: str = ""
    data: str = ""

@dataclass
class Incoming:
    kind: str = "text"               # text|sticker|photo|animation|video|other
    file_id: str = ""
    text: str = ""
    emoji_ids: list = field(default_factory=list)

class Gateway:
    async def send_text(self, chat_id: int, text: str, kb: Kb | None = None) -> int: raise NotImplementedError
    async def edit_text(self, chat_id: int, mid: int, text: str, kb: Kb | None = None, is_media: bool = False) -> None: raise NotImplementedError
    async def edit_kb(self, chat_id: int, mid: int, kb: Kb | None) -> None: raise NotImplementedError
    async def delete(self, chat_id: int, mid: int) -> None: raise NotImplementedError
    async def send_sticker(self, chat_id: int, file_id: str) -> bool: raise NotImplementedError
    async def send_welcome(self, chat_id: int, caption: str, kb: Kb | None, kind: str, file_id: str,
                           asset_path: str) -> tuple: raise NotImplementedError
    async def send_photo_bytes(self, chat_id: int, data: bytes, caption: str, kb: Kb | None = None) -> str: raise NotImplementedError
    async def send_document_bytes(self, chat_id: int, data: bytes, filename: str, caption: str) -> str: raise NotImplementedError
    async def answer_cb(self, cb_id: str, text: str = "", alert: bool = False) -> None: raise NotImplementedError
