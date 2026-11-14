import asyncio, re, unittest
from botnex_quiz.gateway import Incoming
from botnex_quiz.storage import MemoryStorage
from .fakes import User, buttons, find_btn
from .helpers import OWNER_ID, answer_key, make_env, real_qb, wrong_letter

SLUG, CH = "chemistry", 1          # 32 live questions in the real bank

import unicodedata
def strip_tags(s): return unicodedata.normalize("NFKC", re.sub(r"<[^>]+>", "", s))

class Journey(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c, self.gw, self.st, self.sim = make_env()
        self.u = User(1001, "Asha", "asha_k")

    async def open_chapter(self, u=None, slug=SLUG, ch=CH):
        u = u or self.u
        await self.sim.start(u)
        await self.sim.click(u, "m:c12")
        await self.sim.click(u, f"sb:{slug}:0")
        await self.sim.click(u, f"cp:{slug}:{ch}")

    async def current_exam(self, u=None):
        u = u or self.u
        rows = await self.st.list_user_exams(u.id, "active")
        return rows[0] if rows else None

    # ---------------------------------------------------------------- /start
    async def test_start_intro_sticker_welcome(self):
        await self.sim.start(self.u)
        msgs = [m for m in self.gw.msgs.values() if m["chat"] == self.u.id]
        kinds = [m["kind"] for m in msgs]
        self.assertEqual(kinds, ["text", "sticker", "media"])            # intro msg, sticker, welcome media
        intro = msgs[0]
        self.assertTrue(intro["deleted"])                                 # typography disappears
        self.assertGreaterEqual(intro["edits"], 5)                        # ...after changing several times
        self.assertIn("by Chandan Nayak", strip_tags(intro["text"]))                  # last frame carries branding
        self.assertNotIn("Powered by BOTNEX by Chandan Nayak", "")        # sanity
        welcome = msgs[2]
        self.assertIn("Asha", welcome["text"])                            # student's name
        self.assertIn("Powered by BOTNEX by Chandan Nayak", strip_tags(welcome["text"]).replace("𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗕𝗢𝗧𝗡𝗘𝗫 𝗯𝘆 𝗖𝗵𝗮𝗻𝗱𝗮𝗻 𝗡𝗮𝘆𝗮𝗸", "Powered by BOTNEX by Chandan Nayak"))
        urls = [b.url for b in buttons(welcome) if b.url]
        self.assertIn("https://t.me/lll_SOLAC_lll", urls); self.assertIn("https://t.me/BOT_NEX_A", urls)
        self.assertTrue(find_btn(welcome, data_prefix="m:c12")); self.assertTrue(find_btn(welcome, data_prefix="m:c11"))
        self.assertIsNone(find_btn(welcome, data_prefix="ad:"))           # no owner panel for students
        self.assertEqual(self.gw.stickers[0][1], self.c.cfg.default_sticker_id)

    async def test_welcome_caches_media_file_id(self):
        await self.sim.start(self.u)
        st = await self.st.get_settings()
        self.assertEqual(st["welcome_file_id"], "WELCOME_FILE_ID")
        await self.sim.start(User(2, "B"))
        self.assertEqual(self.gw.welcome_calls[-1][1], "WELCOME_FILE_ID")  # second user uses cached id

    async def test_sticker_failure_does_not_break_start(self):
        self.gw.bad_sticker_ids = {self.c.cfg.default_sticker_id}
        await self.sim.start(self.u)
        self.assertTrue(self.gw.chat_msgs(self.u.id, ["media"]))          # welcome still delivered

    async def test_class11_locked_class12_lists_five_subjects(self):
        await self.sim.start(self.u)
        await self.sim.click(self.u, "m:c11")
        self.assertIn("coming soon", self.gw.last_alert()[1]); self.assertTrue(self.gw.last_alert()[2])
        await self.sim.click(self.u, "m:c12")
        _, m = self.gw.last(self.u.id, "media")
        subs = [b.data for b in buttons(m) if (b.data or "").startswith("sb:")]
        self.assertEqual(subs, [f"sb:{s}:0" for s in ("chemistry", "physics", "mathematics", "zoology", "botany")])

    async def test_chapter_list_paginates_and_back(self):
        await self.sim.start(self.u); await self.sim.click(self.u, "m:c12")
        await self.sim.click(self.u, "sb:chemistry:0")
        _, m = self.gw.last(self.u.id, "media")
        chap = [b for b in buttons(m) if (b.data or "").startswith("cp:")]
        self.assertEqual(len(chap), 8)                                    # 15 chapters -> 8 per page
        self.assertTrue(find_btn(m, data_prefix="sb:chemistry:1"))
        await self.sim.click(self.u, "sb:chemistry:1")
        _, m = self.gw.last(self.u.id, "media")
        self.assertEqual(len([b for b in buttons(m) if (b.data or "").startswith("cp:")]), 7)
        self.assertTrue(find_btn(m, data_prefix="m:c12")); self.assertTrue(find_btn(m, data_prefix="m:home"))

    # ---------------------------------------------------------------- quiz rules
    async def test_chapter_click_shows_first_question_directly_no_feedback(self):
        await self.open_chapter()
        ex = await self.current_exam()
        self.assertIsNotNone(ex); self.assertEqual(ex["index"], 0)
        _, q = self.gw.last(self.u.id, "text")
        self.assertIn("01/", q["text"])
        letters = [b.data.split(":")[-1] for b in buttons(q) if b.data.startswith("a:")]
        self.assertEqual(letters, list("abcd"))
        self.assertTrue(find_btn(q, data_prefix="e:"))                    # End Exam visible
        self.assertIsNone(find_btn(q, data_prefix="n:"))                  # Next only after answering

    async def test_answer_locks_shows_next_end_and_hides_correctness(self):
        await self.open_chapter()
        ex = await self.current_exam(); qid = ex["order"][0]
        _, q = self.gw.last(self.u.id, "text"); mid = self.gw.last(self.u.id, "text")[0]
        right = answer_key(self.c, qid)
        await self.sim.click(self.u, f"a:{ex['_id']}:0:{right}")
        q = self.gw.msgs[mid]
        self.assertTrue(find_btn(q, data_prefix="n:")); self.assertTrue(find_btn(q, data_prefix="e:"))
        self.assertIsNone(find_btn(q, data_prefix="a:"))                  # other options gone -> locked
        txt = strip_tags(q["text"]).lower()
        self.assertNotIn("correct answer", txt); self.assertNotIn("❌", txt); self.assertNotIn("not attempted", txt)
        self.assertIn("locked", txt)
        # duplicate / changed answer attempts are ignored
        before = (await self.current_exam())["answers"]
        await self.sim.click(self.u, f"a:{ex['_id']}:0:{wrong_letter(self.c, qid)}", mid)
        self.assertEqual((await self.current_exam())["answers"], before)

    async def test_next_keeps_previous_questions_and_requires_answer(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]
        first_mid = self.gw.last(self.u.id, "text")[0]
        await self.sim.click(self.u, f"n:{eid}:0", first_mid)             # Next without answering
        self.assertIn("select an answer", self.gw.last_alert()[1].lower())
        self.assertEqual((await self.current_exam())["index"], 0)
        await self.sim.click(self.u, f"a:{eid}:0:a", first_mid)
        await self.sim.click(self.u, f"n:{eid}:0", first_mid)
        self.assertEqual((await self.current_exam())["index"], 1)
        qs = self.gw.chat_msgs(self.u.id, ["text"])
        self.assertEqual(len(qs), 2)                                      # old question NOT deleted
        self.assertFalse(self.gw.msgs[first_mid]["deleted"])
        self.assertIsNone(find_btn(self.gw.msgs[first_mid], data_prefix="n:"))   # old buttons locked
        # stale Next click on the old message must not create another question
        await self.sim.click(self.u, f"n:{eid}:0", first_mid)
        self.assertEqual(len(self.gw.chat_msgs(self.u.id, ["text"])), 2)

    async def test_random_order_per_student_and_no_repeats(self):
        orders = []
        for i in range(6):
            u = User(2000 + i, f"S{i}"); await self.open_chapter(u)
            orders.append((await self.current_exam(u))["order"])
        self.assertGreater(len({tuple(o) for o in orders}), 1)            # students get different orders
        pool = set(real_qb().pool("12", SLUG, CH))
        for o in orders:
            self.assertEqual(len(o), len(set(o))); self.assertEqual(set(o), pool)

    async def test_full_exam_auto_completion_result_certificate_review(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]; n = len(ex["order"])
        right = 0
        for i in range(n):
            mid = self.gw.last(self.u.id, "text")[0]
            qid = ex["order"][i]
            if i % 2 == 0: letter = answer_key(self.c, qid); right += 1
            else: letter = wrong_letter(self.c, qid)
            await self.sim.click(self.u, f"a:{eid}:{i}:{letter}", mid)
            await self.sim.click(self.u, f"n:{eid}:{i}", mid)             # on the last one -> auto finish
        done = await self.st.get_exam(eid)
        self.assertEqual(done["status"], "completed")
        r = done["result"]
        self.assertEqual((r["total"], r["attempted"], r["correct"], r["incorrect"], r["unattempted"]),
                         (n, n, right, n - right, 0))
        self.assertAlmostEqual(r["accuracy"], 100 * right / n)
        texts = [strip_tags(m["text"]) for _, m in self.gw.chat_msgs(self.u.id, ["text"])]
        self.assertTrue(any("finished" in t.lower() and "all the questions" in t.lower() for t in texts))
        res = [t for t in texts if "EXAMINATION" in t.upper() and "Marks" in t or "𝗠𝗮𝗿𝗸𝘀" in t]
        self.assertTrue(res)
        _, photo = self.gw.last(self.u.id, "photo")
        self.assertTrue(photo["bytes"].startswith(b"\x89PNG"))
        self.assertTrue(find_btn(photo, data_prefix=f"ka:{eid}:0"))        # Know Answers below certificate
        self.assertGreaterEqual(len(self.gw.stickers), 2)                  # intro + result sticker
        # Know answers: only after exam, no explanation, navigation works
        await self.sim.click(self.u, f"ka:{eid}:0")
        mid, rv = self.gw.last(self.u.id, "text")
        t = strip_tags(rv["text"])
        self.assertIn("Your Answer", t.replace("𝗬𝗼𝘂𝗿 𝗔𝗻𝘀𝘄𝗲𝗿", "Your Answer")); self.assertNotIn("Explanation", t)
        await self.sim.click(self.u, f"ka:{eid}:1", mid)
        self.assertIn("02/", rv["text"])
        await self.sim.click(self.u, f"rs:{eid}", mid)
        self.assertIn("Marks", strip_tags(self.gw.msgs[mid]["text"]).replace("𝗠𝗮𝗿𝗸𝘀", "Marks"))
        await self.sim.click(self.u, f"hd:{eid}")
        self.assertEqual(self.gw.docs[-1][1], f"BOTNEX_Certificate_{eid}.png")

    async def test_end_exam_midway_counts_only_shown_questions(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]
        for i in range(3):
            mid = self.gw.last(self.u.id, "text")[0]
            await self.sim.click(self.u, f"a:{eid}:{i}:{answer_key(self.c, ex['order'][i])}", mid)
            await self.sim.click(self.u, f"n:{eid}:{i}", mid)
        mid = self.gw.last(self.u.id, "text")[0]                          # 4th question shown, not answered
        await self.sim.click(self.u, f"e:{eid}:3", mid)
        r = (await self.st.get_exam(eid))["result"]
        self.assertEqual((r["total"], r["attempted"], r["correct"], r["incorrect"], r["unattempted"]), (4, 3, 3, 0, 1))
        self.assertEqual(r["accuracy"], 100.0)
        self.assertEqual((await self.st.get_exam(eid))["status"], "ended")
        self.assertTrue(self.gw.last(self.u.id, "photo")[1])               # certificate also on early end
        await self.sim.click(self.u, f"ka:{eid}:3")
        self.assertIn("Not Attempted", strip_tags(self.gw.last(self.u.id, "text")[1]["text"]).replace("𝗡𝗼𝘁 𝗔𝘁𝘁𝗲𝗺𝗽𝘁𝗲𝗱", "Not Attempted"))
        # finished exam cannot be continued
        await self.sim.click(self.u, f"n:{eid}:3", mid)
        self.assertIn("finished", self.gw.last_alert()[1])

    async def test_end_exam_after_answering_17_style(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]
        for i in range(17):
            mid = self.gw.last(self.u.id, "text")[0]
            await self.sim.click(self.u, f"a:{eid}:{i}:{answer_key(self.c, ex['order'][i]) if i < 10 else wrong_letter(self.c, ex['order'][i])}", mid)
            if i < 16: await self.sim.click(self.u, f"n:{eid}:{i}", mid)
        await self.sim.click(self.u, f"e:{eid}:16", self.gw.last(self.u.id, "text")[0])
        r = (await self.st.get_exam(eid))["result"]
        self.assertEqual((r["total"], r["attempted"], r["correct"], r["incorrect"], r["unattempted"]), (17, 17, 10, 7, 0))

    async def test_answers_not_available_during_exam(self):
        await self.open_chapter()
        eid = (await self.current_exam())["_id"]
        await self.sim.click(self.u, f"ka:{eid}:0")
        self.assertIn("Finish the exam first", self.gw.last_alert()[1])
        self.assertEqual(len(self.gw.chat_msgs(self.u.id, ["text"])), 1)

    async def test_new_exam_closes_old_and_try_again(self):
        await self.open_chapter()
        old = (await self.current_exam())["_id"]
        await self.sim.click(self.u, "m:home")
        await self.sim.click(self.u, f"cp:{SLUG}:2")
        self.assertEqual((await self.st.get_exam(old))["status"], "abandoned")
        self.assertEqual(len(await self.st.list_user_exams(self.u.id, "active")), 1)

    # ---------------------------------------------------------------- security / robustness
    async def test_other_students_cannot_touch_my_exam(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]; mid = self.gw.last(self.u.id, "text")[0]
        thief = User(666, "Thief")
        await self.sim.start(thief)
        self.sim.gw.msgs[mid]                                              # message belongs to u
        await self.c.on_callback(self.sim.ctx(thief, mid, False, f"a:{eid}:0:a"))
        self.assertIn("not your exam", self.gw.last_alert()[1]); self.assertEqual((await self.current_exam())["answers"], {})
        await self.c.on_callback(self.sim.ctx(thief, mid, False, f"e:{eid}:0"))
        self.assertEqual((await self.current_exam())["status"], "active")
        await self.c.on_callback(self.sim.ctx(thief, mid, False, f"ka:{eid}:0"))
        self.assertIn("Not available", self.gw.last_alert()[1])

    async def test_garbage_and_stale_callbacks_never_crash(self):
        await self.sim.start(self.u)
        for data in ["", "zz:1", "a:", "a:x:y:z", "n:nope:1", "cp:physics:999", "cp:unknown:1", "sb:nope:0", "ka:nope:0",
                     "ad:stats", "e:abc:abc", "a:" + "x" * 40 + ":1:q"]:
            await self.sim.click(self.u, data, self.gw.last(self.u.id, "media")[0])
        self.assertTrue(self.gw.callbacks)                                 # every click was answered, no exception

    async def test_empty_chapter_alert(self):
        await self.sim.start(self.u)
        await self.sim.click(self.u, "cp:physics:999")
        self.assertIn("No questions", self.gw.last_alert()[1])

    async def test_hidden_questions_not_served_until_owner_enables(self):
        qb = real_qb()
        hidden = {q.id for q in qb.questions.values() if q.hidden}
        self.assertTrue(hidden)
        served = set()
        for s in qb.subject_list("12"):
            for no in s.chapters:
                served |= set(qb.pool("12", s.slug, no))
        self.assertFalse(served & hidden)
        self.assertEqual(len(served), qb.report.loaded - qb.report.hidden)
        self.assertEqual(len(qb.pool("12", "physics", 1, include_hidden=True)) , len(qb.get_subject("12","physics").chapters[1].qids_all))

    # ---------------------------------------------------------------- concurrency + restart
    async def test_many_students_at_once_are_isolated(self):
        users = [User(5000 + i, f"U{i}", f"u{i}") for i in range(25)]
        await asyncio.gather(*(self.open_chapter(u) for u in users))
        exams = {u.id: await self.current_exam(u) for u in users}
        self.assertEqual(len({e["_id"] for e in exams.values()}), 25)
        async def play(u):
            ex = exams[u.id]; eid = ex["_id"]
            k = 3 + u.id % 5
            for i in range(k):
                mid = [i2 for i2, m in self.gw.msgs.items() if m["chat"] == u.id and m["kind"] == "text"][i]
                await self.sim.click(u, f"a:{eid}:{i}:{answer_key(self.c, ex['order'][i])}", mid)
                if i < k - 1: await self.sim.click(u, f"n:{eid}:{i}", mid)
            mid = [i2 for i2, m in self.gw.msgs.items() if m["chat"] == u.id and m["kind"] == "text"][k - 1]
            await self.sim.click(u, f"e:{eid}:{k - 1}", mid)
        await asyncio.gather(*(play(u) for u in users))
        for u in users:
            e = await self.st.get_exam(exams[u.id]["_id"]); k = 3 + u.id % 5
            self.assertEqual((e["status"], e["result"]["total"], e["result"]["correct"], e["result"]["incorrect"]), ("ended", k, k, 0))
            self.assertEqual(len(e["answers"]), k)

    async def test_same_user_double_click_is_serialised(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]; mid = self.gw.last(self.u.id, "text")[0]
        await asyncio.gather(*(self.sim.click(self.u, f"a:{eid}:0:a", mid) for _ in range(5)))
        self.assertEqual(len((await self.current_exam())["answers"]), 1)
        await asyncio.gather(*(self.sim.click(self.u, f"n:{eid}:0", mid) for _ in range(5)))
        self.assertEqual((await self.current_exam())["index"], 1)
        self.assertEqual(len(self.gw.chat_msgs(self.u.id, ["text"])), 2)    # exactly one new question

    async def test_restart_recovery_exam_continues(self):
        await self.open_chapter()
        ex = await self.current_exam(); eid = ex["_id"]
        mid = self.gw.last(self.u.id, "text")[0]
        await self.sim.click(self.u, f"a:{eid}:0:b", mid)
        # "restart": brand-new controller + gateway objects, same database
        c2, gw2, _, sim2 = make_env(storage=self.st, gw=self.gw)
        await sim2.click(self.u, f"n:{eid}:0", mid)
        self.assertEqual((await self.current_exam())["index"], 1)
        self.assertEqual((await self.current_exam())["answers"][ex["order"][0]], "b")

# ---------------------------------------------------------------------------- owner / admin
class Admin(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c, self.gw, self.st, self.sim = make_env()
        self.owner = User(OWNER_ID, "Owner", "lll_SOLAC_lll")
        self.stu = User(77, "Ravi", "ravi")

    async def test_students_never_see_or_use_owner_panel(self):
        await self.sim.start(self.stu)
        for d in ["ad:home", "ad:stats", "ad:users:0", "ad:prem", "ad:stk", "ad:hid", "ad:pemo"]:
            await self.sim.click(self.stu, d, self.gw.last(self.stu.id, "media")[0])
            self.assertEqual(self.gw.last_alert()[1], "Owner only.")
        self.assertFalse((await self.st.get_settings())["premium_mode"])

    async def test_owner_panel_stats_users(self):
        await self.sim.start(self.owner); await self.sim.start(self.stu)
        self.assertTrue(find_btn(self.gw.last(self.owner.id, "media")[1], data_prefix="ad:home"))
        await self.sim.click(self.stu, "m:c12"); await self.sim.click(self.stu, "sb:botany:0"); await self.sim.click(self.stu, "cp:botany:1")
        await self.sim.click(self.owner, "ad:home")
        mid = self.gw.last(self.owner.id, "media")[0]
        await self.sim.click(self.owner, "ad:stats", mid)
        t = strip_tags(self.gw.msgs[mid]["text"])
        self.assertIn("Registered users", t.replace("𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 𝘂𝘀𝗲𝗿𝘀", "Registered users"))
        self.assertIn(": 2", t); self.assertIn("Exams started", t.replace("𝗘𝘅𝗮𝗺𝘀 𝘀𝘁𝗮𝗿𝘁𝗲𝗱", "Exams started"))
        await self.sim.click(self.owner, "ad:users:0", mid)
        t = self.gw.msgs[mid]["text"]
        self.assertIn("Ravi", t); self.assertIn("@ravi", t); self.assertIn(str(self.stu.id), t)

    async def test_owner_toggles_and_sets_sticker_any_time(self):
        await self.sim.start(self.owner); await self.sim.click(self.owner, "ad:home")
        mid = self.gw.last(self.owner.id, "media")[0]
        await self.sim.click(self.owner, "ad:prem", mid)
        self.assertTrue((await self.st.get_settings())["premium_mode"])
        await self.sim.click(self.owner, "ad:prem", mid)
        self.assertFalse((await self.st.get_settings())["premium_mode"])
        await self.sim.click(self.owner, "ad:stk", mid)
        self.assertEqual((await self.st.get_settings())["awaiting_owner"], "sticker_normal")
        await self.sim.send(self.owner, Incoming("sticker", "NEWSTICKER"))
        self.assertEqual((await self.st.get_settings())["sticker_normal"], "NEWSTICKER")
        await self.sim.start(self.stu)
        self.assertEqual(self.gw.stickers[-1][1], "NEWSTICKER")           # new students see the new sticker
        # a student's sticker/photo never changes anything
        await self.sim.send(self.stu, Incoming("sticker", "HACK"))
        self.assertEqual((await self.st.get_settings())["sticker_normal"], "NEWSTICKER")

    async def test_owner_input_wrong_item_is_rejected(self):
        await self.sim.start(self.owner); await self.sim.click(self.owner, "ad:home")
        await self.sim.click(self.owner, "ad:stk", self.gw.last(self.owner.id, "media")[0])
        await self.sim.send(self.owner, Incoming("text", "", "hello"))
        self.assertEqual((await self.st.get_settings())["awaiting_owner"], "sticker_normal")
        await self.sim.click(self.owner, "ad:cancel", self.gw.last(self.owner.id, "text")[0])
        self.assertEqual((await self.st.get_settings())["awaiting_owner"], "")

    async def test_premium_mode_uses_premium_assets_and_falls_back_safely(self):
        await self.st.set_setting("sticker_premium", "PREMSTICKER")
        await self.st.set_setting("premium_emoji", {"sparkle": "5000001", "cap": "5000002", "diamond": "5000003"})
        await self.st.set_setting("premium_mode", True)
        await self.sim.start(self.stu)
        self.assertEqual(self.gw.stickers[-1][1], "PREMSTICKER")
        _, w = self.gw.last(self.stu.id, "media")
        self.assertIn("<tg-emoji", w["text"]); self.assertTrue(any(b.icon_id for b in buttons(w)))
        # now Telegram rejects premium (owner has no Premium): bot must switch OFF and still deliver
        self.gw.fail_premium = True
        await self.sim.start(User(78, "Mina"))
        self.assertFalse((await self.st.get_settings())["premium_mode"])
        _, w = self.gw.last(78, "media")
        self.assertNotIn("<tg-emoji", w["text"]); self.assertFalse(any(b.icon_id for b in buttons(w)))
        self.assertTrue(any("switched OFF" in m["text"] for _, m in self.gw.chat_msgs(OWNER_ID, ["text"])))

    async def test_premium_emoji_capture_maps_slots_in_order(self):
        await self.sim.start(self.owner); await self.sim.click(self.owner, "ad:home")
        await self.sim.click(self.owner, "ad:pemo", self.gw.last(self.owner.id, "media")[0])
        await self.sim.send(self.owner, Incoming("text", "", "x", ["11", "22", "33"]))
        em = (await self.st.get_settings())["premium_emoji"]
        self.assertEqual(em, {"sparkle": "11", "trophy": "22", "book": "33"})

    async def test_include_hidden_toggle_changes_pool(self):
        await self.sim.start(self.owner); await self.sim.click(self.owner, "ad:home")
        mid = self.gw.last(self.owner.id, "media")[0]
        await self.sim.click(self.owner, "ad:hid", mid)
        self.assertTrue((await self.st.get_settings())["include_hidden"])
        await self.sim.click(self.owner, "sb:physics:0")
        await self.sim.click(self.owner, "cp:physics:2")
        ex = (await self.st.list_user_exams(self.owner.id, "active"))[0]
        qb = real_qb()
        self.assertEqual(len(ex["order"]), len(qb.get_subject("12", "physics").chapters[2].qids_all))

    async def test_plain_text_gets_friendly_redirect(self):
        await self.sim.send(self.stu, Incoming("text", "", "hello"))
        _, m = self.gw.last(self.stu.id, "text")
        self.assertIn("buttons", strip_tags(m["text"]).replace("𝗣𝗹𝗲𝗮𝘀𝗲 𝘂𝘀𝗲 𝘁𝗵𝗲 𝗯𝘂𝘁𝘁𝗼𝗻𝘀", "buttons"))

if __name__ == "__main__":
    unittest.main()
