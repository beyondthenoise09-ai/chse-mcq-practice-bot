"""Test doubles: FakeGateway (records everything Telegram would show) and FakeMotor (in-memory Mongo)."""
from __future__ import annotations
import copy
from botnex_quiz.gateway import Ctx, Gateway, Incoming, PremiumFailed

# ------------------------------------------------------------------ fake telegram
class FakeGateway(Gateway):
    def __init__(self):
        self.msgs = {}          # mid -> dict(chat, kind, text, kb, deleted, edits)
        self.next = 100
        self.callbacks = []     # (cb_id, text, alert)
        self.stickers = []      # (chat, file_id)
        self.docs = []
        self.fail_premium = False
        self.bad_sticker_ids = set()
        self.welcome_calls = []

    def _premium(self, text, kb):
        return "<tg-emoji" in (text or "") or any(b.icon_id for r in (kb or []) for b in r)

    def _new(self, chat, kind, text, kb):
        self.next += 1
        self.msgs[self.next] = dict(chat=chat, kind=kind, text=text, kb=kb, deleted=False, edits=0)
        return self.next

    async def send_text(self, chat_id, text, kb=None):
        if self.fail_premium and self._premium(text, kb):
            raise PremiumFailed("premium")
        return self._new(chat_id, "text", text, kb)

    async def edit_text(self, chat_id, mid, text, kb=None, is_media=False):
        if self.fail_premium and self._premium(text, kb):
            raise PremiumFailed("premium")
        m = self.msgs[mid]
        assert not m["deleted"], "edit on deleted message"
        m.update(text=text, kb=kb); m["edits"] += 1

    async def edit_kb(self, chat_id, mid, kb):
        self.msgs[mid]["kb"] = kb

    async def delete(self, chat_id, mid):
        self.msgs[mid]["deleted"] = True

    async def send_sticker(self, chat_id, file_id):
        if file_id in self.bad_sticker_ids:
            return False
        self.stickers.append((chat_id, file_id)); self._new(chat_id, "sticker", file_id, None)
        return True

    async def send_welcome(self, chat_id, caption, kb, kind, file_id, asset_path):
        if self.fail_premium and self._premium(caption, kb):
            raise PremiumFailed("premium")
        self.welcome_calls.append((kind, file_id, asset_path))
        mid = self._new(chat_id, "media", caption, kb)
        return "animation", file_id or "WELCOME_FILE_ID"

    async def send_photo_bytes(self, chat_id, data, caption, kb=None):
        self._new(chat_id, "photo", caption, kb); self.msgs[self.next]["bytes"] = data
        return "PHOTO_ID"

    async def send_document_bytes(self, chat_id, data, filename, caption):
        self.docs.append((chat_id, filename, len(data))); return "DOC_ID"

    async def answer_cb(self, cb_id, text="", alert=False):
        self.callbacks.append((cb_id, text, alert))

    # ---- helpers for tests
    def chat_msgs(self, chat, kinds=None):
        return [(i, m) for i, m in self.msgs.items() if m["chat"] == chat and not m["deleted"]
                and (kinds is None or m["kind"] in kinds)]

    def last(self, chat, kind=None):
        rows = [(i, m) for i, m in self.msgs.items() if m["chat"] == chat and (kind is None or m["kind"] == kind)]
        return rows[-1] if rows else (None, None)

    def last_alert(self):
        return self.callbacks[-1] if self.callbacks else None

def buttons(msg):
    return [b for row in (msg["kb"] or []) for b in row]

def find_btn(msg, *, data_prefix=None, text_has=None):
    for b in buttons(msg):
        if data_prefix and (b.data or "").startswith(data_prefix):
            return b
        if text_has and text_has in b.text:
            return b
    return None

class User:
    def __init__(self, uid, name="Student", username=""):
        self.id, self.name, self.username = uid, name, username

class Sim:
    """Drives a Controller like Telegram would."""
    def __init__(self, ctrl, gw):
        self.c, self.gw, self.n = ctrl, gw, 0

    def ctx(self, u, mid=0, is_media=False, data=""):
        self.n += 1
        return Ctx(u.id, u.name, u.username, u.id, mid, is_media, f"cb{self.n}", data)

    async def start(self, u):
        await self.c.on_start(self.ctx(u))

    async def click(self, u, data, mid=None):
        """Press a button. If mid is None, uses the newest message of this chat that has that button."""
        if mid is None:
            for i, m in sorted(self.gw.msgs.items(), reverse=True):
                if m["chat"] == u.id and not m["deleted"] and any(b.data == data for b in buttons(m)):
                    mid = i; break
        if mid is None:
            mid = max(i for i, m in self.gw.msgs.items() if m["chat"] == u.id)
        m = self.gw.msgs[mid]
        await self.c.on_callback(self.ctx(u, mid, m["kind"] in ("media", "photo"), data))

    async def send(self, u, inc):
        await self.c.on_message(self.ctx(u), inc)

# ------------------------------------------------------------------ fake mongo (motor-like)
def _match(doc, flt):
    return all(doc.get(k) == v for k, v in flt.items())

class FakeCursor:
    def __init__(self, rows): self.rows = rows
    async def to_list(self, length=None): return [copy.deepcopy(r) for r in self.rows[:length]]

class FakeCollection:
    def __init__(self): self.docs = {}
    async def create_index(self, *a, **k): return "idx"
    async def find_one(self, flt):
        for d in self.docs.values():
            if _match(d, flt): return copy.deepcopy(d)
        return None
    async def insert_one(self, doc):
        assert doc["_id"] not in self.docs; self.docs[doc["_id"]] = copy.deepcopy(doc)
    async def update_one(self, flt, upd, upsert=False):
        target = next((d for d in self.docs.values() if _match(d, flt)), None)
        if target is None:
            if not upsert: return
            target = {k: v for k, v in flt.items()}
            target.update(copy.deepcopy(upd.get("$setOnInsert", {})))
            self.docs[target["_id"]] = target
        for k, v in upd.get("$set", {}).items(): target[k] = copy.deepcopy(v)
        for k, v in upd.get("$inc", {}).items(): target[k] = target.get(k, 0) + v
    def find(self, flt):
        return FakeCursor([d for d in self.docs.values() if _match(d, flt)])
    async def count_documents(self, flt):
        return sum(1 for d in self.docs.values() if _match(d, flt))

class FakeDB(dict):
    def __missing__(self, k): self[k] = FakeCollection(); return self[k]

class FakeMotorClient(dict):
    def __missing__(self, k): self[k] = FakeDB(); return self[k]
