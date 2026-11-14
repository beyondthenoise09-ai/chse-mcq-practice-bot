"""Storage layer: MongoStorage (production) and MemoryStorage (tests / quick local run).

Only equality filters and $set/$inc/$setOnInsert are used, so both back-ends behave the same.
Collections: users, exams, settings.
"""
from __future__ import annotations
import copy
import logging
import time
from typing import Any

log = logging.getLogger("botnex.storage")

DEFAULT_SETTINGS: dict = {
    "premium_mode": False,          # owner toggles; OFF until owner has Telegram Premium
    "include_hidden": False,        # owner can enable flagged questions
    "sticker_normal": "",
    "sticker_premium": "",
    "premium_emoji": {},            # slot -> custom emoji id
    "welcome_file_id": "",          # cached/owner-set welcome media
    "welcome_kind": "",             # animation | photo
    "awaiting_owner": "",           # owner panel multi-step input state
}

def now() -> int:
    return int(time.time())

class Storage:
    async def init(self) -> None: ...
    async def upsert_user(self, uid: int, first_name: str, username: str) -> dict: ...
    async def get_user(self, uid: int) -> dict | None: ...
    async def inc_user(self, uid: int, field: str, n: int = 1) -> None: ...
    async def list_users(self, skip: int, limit: int) -> list: ...
    async def count_users(self) -> int: ...
    async def count_active_users(self, since: int) -> int: ...
    async def create_exam(self, doc: dict) -> None: ...
    async def get_exam(self, eid: str) -> dict | None: ...
    async def update_exam(self, eid: str, fields: dict) -> None: ...
    async def list_user_exams(self, uid: int, status: str) -> list: ...
    async def count_exams(self, **flt: Any) -> int: ...
    async def list_exams(self, **flt: Any) -> list: ...
    async def get_settings(self) -> dict: ...
    async def set_setting(self, key: str, value: Any) -> None: ...

# ------------------------------------------------------------------ memory
class MemoryStorage(Storage):
    def __init__(self) -> None:
        self.users: dict[int, dict] = {}
        self.exams: dict[str, dict] = {}
        self.settings: dict = {}

    async def upsert_user(self, uid, first_name, username):
        u = self.users.get(uid)
        if u is None:
            u = {"_id": uid, "first_name": first_name, "username": username,
                 "registered_at": now(), "attempts": 0, "completed": 0}
            self.users[uid] = u
        u.update(first_name=first_name, username=username, last_active=now())
        return dict(u)

    async def get_user(self, uid):
        u = self.users.get(uid)
        return dict(u) if u else None

    async def inc_user(self, uid, field, n=1):
        if uid in self.users:
            self.users[uid][field] = self.users[uid].get(field, 0) + n

    async def list_users(self, skip, limit):
        us = sorted(self.users.values(), key=lambda u: u.get("registered_at", 0))
        return [dict(u) for u in us[skip:skip + limit]]

    async def count_users(self):
        return len(self.users)

    async def count_active_users(self, since):
        return sum(1 for u in self.users.values() if u.get("last_active", 0) >= since)

    async def create_exam(self, doc):
        self.exams[doc["_id"]] = dict(doc)

    async def get_exam(self, eid):
        e = self.exams.get(eid)
        return _copy_exam(e) if e else None

    async def update_exam(self, eid, fields):
        if eid in self.exams:
            self.exams[eid].update(fields)

    async def list_user_exams(self, uid, status):
        return [_copy_exam(e) for e in self.exams.values() if e["user_id"] == uid and e["status"] == status]

    def _match(self, flt):
        return [e for e in self.exams.values() if all(e.get(k) == v for k, v in flt.items())]

    async def count_exams(self, **flt):
        return len(self._match(flt))

    async def list_exams(self, **flt):
        return [_copy_exam(e) for e in self._match(flt)]

    async def get_settings(self):
        s = copy.deepcopy(DEFAULT_SETTINGS)
        s.update(copy.deepcopy(self.settings))
        return s

    async def set_setting(self, key, value):
        self.settings[key] = copy.deepcopy(value)

def _copy_exam(e: dict) -> dict:
    d = dict(e)
    d["answers"] = dict(e.get("answers", {}))
    d["order"] = list(e.get("order", []))
    return d

# ------------------------------------------------------------------- mongo
class MongoStorage(Storage):
    def __init__(self, uri: str = "", db_name: str = "botnex_quiz", client: Any = None) -> None:
        if client is None:
            from motor.motor_asyncio import AsyncIOMotorClient   # imported lazily (not needed in tests)
            client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000)
        self.db = client[db_name]
        self.users = self.db["users"]
        self.exams = self.db["exams"]
        self.cfg = self.db["settings"]

    async def init(self):
        try:
            await self.users.create_index("last_active")
            await self.exams.create_index("user_id")
            await self.exams.create_index("status")
        except Exception as e:
            log.error("Index creation failed (continuing): %s", e)

    async def upsert_user(self, uid, first_name, username):
        await self.users.update_one(
            {"_id": uid},
            {"$set": {"first_name": first_name, "username": username, "last_active": now()},
             "$setOnInsert": {"registered_at": now(), "attempts": 0, "completed": 0}},
            upsert=True)
        return await self.users.find_one({"_id": uid})

    async def get_user(self, uid):
        return await self.users.find_one({"_id": uid})

    async def inc_user(self, uid, field, n=1):
        await self.users.update_one({"_id": uid}, {"$inc": {field: n}})

    async def list_users(self, skip, limit):
        rows = await self.users.find({}).to_list(length=100000)
        rows.sort(key=lambda u: u.get("registered_at", 0))
        return rows[skip:skip + limit]

    async def count_users(self):
        return await self.users.count_documents({})

    async def count_active_users(self, since):
        rows = await self.users.find({}).to_list(length=100000)
        return sum(1 for u in rows if u.get("last_active", 0) >= since)

    async def create_exam(self, doc):
        await self.exams.insert_one(dict(doc))

    async def get_exam(self, eid):
        return await self.exams.find_one({"_id": eid})

    async def update_exam(self, eid, fields):
        await self.exams.update_one({"_id": eid}, {"$set": fields})

    async def list_user_exams(self, uid, status):
        return await self.exams.find({"user_id": uid, "status": status}).to_list(length=1000)

    async def count_exams(self, **flt):
        return await self.exams.count_documents(flt)

    async def list_exams(self, **flt):
        return await self.exams.find(flt).to_list(length=100000)

    async def get_settings(self):
        s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_SETTINGS.items()}
        doc = await self.cfg.find_one({"_id": "main"}) or {}
        for k, v in doc.items():
            if k != "_id":
                s[k] = v
        return s

    async def set_setting(self, key, value):
        await self.cfg.update_one({"_id": "main"}, {"$set": {key: value}}, upsert=True)
