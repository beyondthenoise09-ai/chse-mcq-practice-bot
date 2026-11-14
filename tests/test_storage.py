import unittest
from botnex_quiz.storage import MemoryStorage, MongoStorage, now
from .fakes import FakeMotorClient

class StorageContract:
    async def asyncSetUp(self):
        self.s = self.make(); await self.s.init()
    async def test_user_lifecycle(self):
        u = await self.s.upsert_user(5, "Asha", "asha")
        self.assertEqual(u["attempts"], 0)
        await self.s.inc_user(5, "attempts", 2)
        u2 = await self.s.upsert_user(5, "Asha K", "asha2")
        self.assertEqual((u2["first_name"], u2["username"], u2["attempts"]), ("Asha K", "asha2", 2))
        self.assertEqual(await self.s.count_users(), 1)
        self.assertEqual(await self.s.count_active_users(now() - 10), 1)
        self.assertEqual(len(await self.s.list_users(0, 10)), 1)
    async def test_exam_roundtrip_and_isolation(self):
        await self.s.create_exam({"_id": "e1", "user_id": 1, "status": "active", "answers": {}, "order": ["a", "b"], "subject_slug": "physics"})
        await self.s.create_exam({"_id": "e2", "user_id": 2, "status": "active", "answers": {}, "order": ["a"], "subject_slug": "chemistry"})
        await self.s.update_exam("e1", {"answers": {"a": "b"}, "status": "completed"})
        e1, e2 = await self.s.get_exam("e1"), await self.s.get_exam("e2")
        self.assertEqual(e1["answers"], {"a": "b"}); self.assertEqual(e2["answers"], {})
        self.assertEqual(await self.s.count_exams(), 2)
        self.assertEqual(await self.s.count_exams(status="completed"), 1)
        self.assertEqual([e["_id"] for e in await self.s.list_user_exams(2, "active")], ["e2"])
        self.assertIsNone(await self.s.get_exam("nope"))
    async def test_settings_defaults_and_persist(self):
        st = await self.s.get_settings()
        self.assertFalse(st["premium_mode"]); self.assertFalse(st["include_hidden"])
        await self.s.set_setting("premium_mode", True); await self.s.set_setting("premium_emoji", {"sparkle": "1"})
        st = await self.s.get_settings()
        self.assertTrue(st["premium_mode"]); self.assertEqual(st["premium_emoji"], {"sparkle": "1"})
        st["premium_emoji"]["x"] = "y"                            # mutating the copy must not leak
        self.assertNotIn("x", (await self.s.get_settings())["premium_emoji"])

class TestMemory(StorageContract, unittest.IsolatedAsyncioTestCase):
    def make(self): return MemoryStorage()

class TestMongoWithFakeMotor(StorageContract, unittest.IsolatedAsyncioTestCase):
    def make(self): return MongoStorage(client=FakeMotorClient(), db_name="t")
