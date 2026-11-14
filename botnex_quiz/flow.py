"""BOTNEX Quiz - the whole bot behaviour (Telegram independent).

Journey: /start -> intro -> sticker -> welcome -> Class 12th -> Subject -> Chapter ->
questions (random order per student, one answer, no feedback) -> Next / End Exam ->
auto-complete when the pool is exhausted -> result -> sticker -> certificate -> Know Answers.
"""
from __future__ import annotations
import asyncio
import logging
import os
import uuid
from collections import Counter
from . import ui
from .gateway import Btn, Ctx, Gateway, Incoming, PremiumFailed
from .questionbank import QuestionBank
from .storage import Storage, now
from .styling import bold, esc, LINE
from .theme import SLOTS, Theme

log = logging.getLogger("botnex.flow")
CLS = "12"

class Controller:
    def __init__(self, cfg, qb: QuestionBank, storage: Storage, gw: Gateway, cert_renderer,
                 intro_delay: float = 0.9) -> None:
        self.cfg, self.qb, self.st, self.gw = cfg, qb, storage, gw
        self.render_cert = cert_renderer
        self.intro_delay = intro_delay
        self._locks: dict[int, asyncio.Lock] = {}

    # ---------------------------------------------------------------- helpers
    def _lock(self, uid: int) -> asyncio.Lock:
        return self._locks.setdefault(uid, asyncio.Lock())

    def is_owner(self, uid: int) -> bool:
        return bool(self.cfg.owner_id) and uid == self.cfg.owner_id

    async def _with_theme(self, fn):
        """Run fn(theme). If Telegram rejects premium content, switch premium OFF and retry normally."""
        s = await self.st.get_settings()
        th = Theme.from_settings(s)
        try:
            return await fn(th, s)
        except PremiumFailed:
            if not th.premium:
                raise
            log.warning("Premium content rejected by Telegram -> premium mode switched OFF")
            await self.st.set_setting("premium_mode", False)
            await self._notify_owner("⚠️ Premium mode was switched OFF automatically because Telegram "
                                     "rejected premium emoji/icons (the account needs Telegram Premium). "
                                     "Turn it on again from the Owner Panel after you get Premium.")
            s["premium_mode"] = False
            return await fn(Theme.normal(), s)

    async def _notify_owner(self, text: str) -> None:
        if not self.cfg.owner_id:
            return
        try:
            await self.gw.send_text(self.cfg.owner_id, text, None)
        except Exception as e:
            log.error("Could not notify owner: %s", e)

    def _name(self, ctx: Ctx) -> str:
        return (ctx.first_name or ctx.username or "Student").strip() or "Student"

    # ---------------------------------------------------------------- /start
    async def on_start(self, ctx: Ctx) -> None:
        async with self._lock(ctx.user_id):
            await self.st.upsert_user(ctx.user_id, self._name(ctx), ctx.username or "")
            await self._intro(ctx)

    async def _intro(self, ctx: Ctx) -> None:
        # Stage 1: animated typography (appear / change / disappear)
        s = await self.st.get_settings()
        th = Theme.from_settings(s)
        frames = ui.intro_frames(th)
        mid = None
        try:
            try:
                mid = await self.gw.send_text(ctx.chat_id, frames[0], None)
                for f in frames[1:]:
                    await asyncio.sleep(self.intro_delay)
                    await self.gw.edit_text(ctx.chat_id, mid, f, None)
                await asyncio.sleep(self.intro_delay)
            except PremiumFailed:
                raise
            except Exception as e:
                log.warning("Intro animation interrupted: %s", e)
            if mid is not None:
                try:
                    await self.gw.delete(ctx.chat_id, mid)
                except Exception:
                    pass
        except PremiumFailed:
            await self.st.set_setting("premium_mode", False)
            await self._notify_owner("⚠️ Premium mode switched OFF automatically (Telegram rejected premium emoji).")
        # Stage 2: sticker
        await self._send_sticker(ctx.chat_id)
        await asyncio.sleep(self.intro_delay / 2)
        # Stage 3: welcome media + message + buttons
        await self._send_welcome(ctx)

    async def _send_sticker(self, chat_id: int) -> None:
        s = await self.st.get_settings()
        use_premium = bool(s.get("premium_mode")) and bool(s.get("sticker_premium"))
        sid = s["sticker_premium"] if use_premium else (s.get("sticker_normal") or self.cfg.default_sticker_id)
        for candidate in (sid, self.cfg.default_sticker_id):
            if not candidate:
                continue
            try:
                if await self.gw.send_sticker(chat_id, candidate):
                    return
            except Exception as e:
                log.warning("Sticker send failed (%s): %s", candidate[:12], e)

    def _asset(self) -> str:
        for n in ("welcome.mp4", "welcome.jpg"):
            p = self.cfg.assets_dir / n
            if p.exists():
                return str(p)
        return ""

    async def _send_welcome(self, ctx: Ctx) -> None:
        async def go(th: Theme, s: dict):
            cap = ui.welcome_caption(th, self._name(ctx), self.cfg.bot_display_name)
            kb = ui.welcome_kb(th, self.cfg, self.is_owner(ctx.user_id))
            kind, fid = await self.gw.send_welcome(ctx.chat_id, cap, kb, s.get("welcome_kind", ""),
                                                   s.get("welcome_file_id", ""), self._asset())
            if fid and not s.get("welcome_file_id"):
                await self.st.set_setting("welcome_file_id", fid)
                await self.st.set_setting("welcome_kind", kind)
        await self._with_theme(go)

    # ---------------------------------------------------------------- callbacks
    async def on_callback(self, ctx: Ctx) -> None:
        data = ctx.data or ""
        try:
            async with self._lock(ctx.user_id):
                await self.st.upsert_user(ctx.user_id, self._name(ctx), ctx.username or "")
                await self._route(ctx, data)
        except PremiumFailed:
            raise
        except Exception:
            log.exception("Callback failed: %s", data)
            try:
                await self.gw.answer_cb(ctx.cb_id, "Something went wrong. Please try again.", True)
            except Exception:
                pass

    async def _route(self, ctx: Ctx, data: str) -> None:
        p = data.split(":")
        k = p[0]
        if k == "x":
            return await self.gw.answer_cb(ctx.cb_id)
        if k == "m":
            return await self._menu(ctx, p[1] if len(p) > 1 else "home")
        if k == "sb":
            return await self._chapters(ctx, p[1], int(p[2]) if len(p) > 2 else 0)
        if k == "cp":
            return await self._start_exam(ctx, p[1], int(p[2]))
        if k == "ag":
            return await self._start_exam(ctx, p[1], int(p[2]))
        if k == "a":
            return await self._answer(ctx, p[1], int(p[2]), p[3])
        if k == "n":
            return await self._next(ctx, p[1], int(p[2]))
        if k == "e":
            return await self._end(ctx, p[1], int(p[2]))
        if k == "ka":
            return await self._review(ctx, p[1], int(p[2]))
        if k == "rs":
            return await self._back_to_result(ctx, p[1])
        if k == "hd":
            return await self._hd_certificate(ctx, p[1])
        if k == "ad":
            return await self._admin(ctx, p[1:])
        await self.gw.answer_cb(ctx.cb_id, "This button has expired. Please send /start", True)

    # ---------------------------------------------------------------- menus
    async def _show(self, ctx: Ctx, th: Theme, text: str, kb: list) -> None:
        await self.gw.edit_text(ctx.chat_id, ctx.message_id, text, kb, ctx.is_media)

    async def _menu(self, ctx: Ctx, where: str) -> None:
        if where == "c11":
            return await self.gw.answer_cb(ctx.cb_id, "Class 11th is coming soon 🔒", True)
        await self.gw.answer_cb(ctx.cb_id)
        async def go(th, s):
            if where == "home":
                cap = ui.welcome_caption(th, self._name(ctx), self.cfg.bot_display_name)
                await self._show(ctx, th, cap, ui.welcome_kb(th, self.cfg, self.is_owner(ctx.user_id)))
            else:
                subs = self.qb.subject_list(CLS)
                inc = bool(s.get("include_hidden"))
                counts = {x.slug: self.qb.count(CLS, x.slug, include_hidden=inc) for x in subs}
                subs = [x for x in subs if counts[x.slug] > 0]
                await self._show(ctx, th, ui.class_menu_text(th), ui.subjects_kb(th, subs, counts))
        await self._with_theme(go)

    async def _chapters(self, ctx: Ctx, slug: str, page: int) -> None:
        sub = self.qb.get_subject(CLS, slug)
        if not sub:
            return await self.gw.answer_cb(ctx.cb_id, "Subject not found", True)
        await self.gw.answer_cb(ctx.cb_id)
        async def go(th, s):
            inc = bool(s.get("include_hidden"))
            live = {no: len(self.qb.pool(CLS, slug, no, inc)) for no in sub.chapters}
            kb, pg, pages = ui.chapters_kb(th, sub, live, page)
            await self._show(ctx, th, ui.chapters_text(th, sub, pg, pages), kb)
        await self._with_theme(go)

    # ---------------------------------------------------------------- exam
    async def _start_exam(self, ctx: Ctx, slug: str, chno: int) -> None:
        s = await self.st.get_settings()
        pool = self.qb.pool(CLS, slug, chno, bool(s.get("include_hidden")))
        sub = self.qb.get_subject(CLS, slug)
        if not pool or not sub:
            return await self.gw.answer_cb(ctx.cb_id, "No questions available in this chapter yet.", True)
        await self.gw.answer_cb(ctx.cb_id, "Exam started! Good luck 🍀")
        # a student has one active exam: close any older one quietly
        for old in await self.st.list_user_exams(ctx.user_id, "active"):
            await self.st.update_exam(old["_id"], {"status": "abandoned", "finished_at": now()})
            if old.get("last_msg_id"):
                try:
                    await self.gw.edit_kb(old["chat_id"], old["last_msg_id"],
                                          ui.locked_kb(old["answers"].get(old["order"][old["index"]])))
                except Exception:
                    pass
        eid = uuid.uuid4().hex[:10]
        ex = {"_id": eid, "user_id": ctx.user_id, "chat_id": ctx.chat_id, "cls": CLS,
              "subject_slug": slug, "subject": sub.name, "chapter_no": chno,
              "chapter": sub.chapters[chno].name, "order": self.qb.random_order(pool),
              "index": 0, "answers": {}, "status": "active", "started_at": now(),
              "pool_size": len(pool), "name": self._name(ctx), "username": ctx.username or "",
              "last_msg_id": 0}
        await self.st.create_exam(ex)
        await self.st.inc_user(ctx.user_id, "attempts", 1)
        await self._send_question(ctx.chat_id, ex)

    async def _send_question(self, chat_id: int, ex: dict) -> None:
        async def go(th, s):
            qid = ex["order"][ex["index"]]
            q = self.qb.get(qid)
            text = ui.question_text(th, ex, q, ex["index"] + 1, len(ex["order"]), None)
            kb = ui.question_kb(th, ex["_id"], ex["index"], None)
            mid = await self.gw.send_text(chat_id, text, kb)
            ex["last_msg_id"] = mid
            await self.st.update_exam(ex["_id"], {"last_msg_id": mid, "index": ex["index"]})
        await self._with_theme(go)

    async def _load_active(self, ctx: Ctx, eid: str, idx: int | None = None):
        """Common checks: exam exists, belongs to this user, still active, button is current."""
        ex = await self.st.get_exam(eid)
        if not ex:
            await self.gw.answer_cb(ctx.cb_id, "This exam is no longer available.", True)
            return None
        if ex["user_id"] != ctx.user_id:                      # never let someone drive another student's exam
            log.warning("User %s tried to use exam of %s", ctx.user_id, ex["user_id"])
            await self.gw.answer_cb(ctx.cb_id, "This is not your exam.", True)
            return None
        if ex["status"] != "active":
            await self.gw.answer_cb(ctx.cb_id, "This exam is already finished.", True)
            return None
        if idx is not None and idx != ex["index"]:
            await self.gw.answer_cb(ctx.cb_id, "Please use the latest question.", True)
            return None
        return ex

    async def _answer(self, ctx: Ctx, eid: str, idx: int, letter: str) -> None:
        if letter not in ("a", "b", "c", "d"):
            return await self.gw.answer_cb(ctx.cb_id, "Invalid option", True)
        ex = await self._load_active(ctx, eid, idx)
        if not ex:
            return
        qid = ex["order"][idx]
        if qid in ex["answers"]:
            return await self.gw.answer_cb(ctx.cb_id, "Answer already locked 🔒", False)
        ex["answers"][qid] = letter
        await self.st.update_exam(eid, {"answers": ex["answers"]})
        await self.gw.answer_cb(ctx.cb_id, f"Answer {letter.upper()} saved ✅")
        async def go(th, s):
            q = self.qb.get(qid)
            text = ui.question_text(th, ex, q, idx + 1, len(ex["order"]), letter)
            await self.gw.edit_text(ctx.chat_id, ctx.message_id, text, ui.question_kb(th, eid, idx, letter))
        await self._with_theme(go)

    async def _next(self, ctx: Ctx, eid: str, idx: int) -> None:
        ex = await self._load_active(ctx, eid, idx)
        if not ex:
            return
        qid = ex["order"][idx]
        if qid not in ex["answers"]:
            return await self.gw.answer_cb(ctx.cb_id, "Please select an answer first.", True)
        await self.gw.answer_cb(ctx.cb_id)
        try:                                                  # keep old question in chat, just lock its buttons
            await self.gw.edit_kb(ctx.chat_id, ctx.message_id, ui.locked_kb(ex["answers"][qid]))
        except Exception:
            pass
        if idx + 1 >= len(ex["order"]):
            return await self._finish(ctx.chat_id, ex, "completed")
        ex["index"] = idx + 1
        await self.st.update_exam(eid, {"index": ex["index"]})
        await self._send_question(ctx.chat_id, ex)

    async def _end(self, ctx: Ctx, eid: str, idx: int) -> None:
        ex = await self._load_active(ctx, eid, idx)
        if not ex:
            return
        await self.gw.answer_cb(ctx.cb_id, "Exam ended")
        try:
            await self.gw.edit_kb(ctx.chat_id, ctx.message_id,
                                  ui.locked_kb(ex["answers"].get(ex["order"][idx])))
        except Exception:
            pass
        await self._finish(ctx.chat_id, ex, "ended")

    async def _finish(self, chat_id: int, ex: dict, status: str) -> None:
        r = ui.compute_result(ex, self.qb)
        await self.st.update_exam(ex["_id"], {"status": status, "finished_at": now(), "result": r})
        await self.st.inc_user(ex["user_id"], "completed", 1)
        ex.update(status=status, result=r, finished_at=now())
        await self._send_results(chat_id, ex, r, status)

    async def _send_results(self, chat_id: int, ex: dict, r: dict, status: str) -> None:
        async def go(th, s):
            if status == "completed":
                await self.gw.send_text(chat_id, ui.completed_text(th), None)
            await self.gw.send_text(chat_id, ui.result_text(th, ex, r, status), None)
        await self._with_theme(go)
        await self._send_sticker(chat_id)
        # certificate (drawn by code)
        try:
            data = await self._cert_bytes(ex, r)
            async def go2(th, s):
                fid = await self.gw.send_photo_bytes(chat_id, data, ui.cert_caption(th, ex, r),
                                                     ui.result_kb(th, ex))
                await self.st.update_exam(ex["_id"], {"cert_file_id": fid or ""})
            await self._with_theme(go2)
        except Exception:
            log.exception("Certificate failed")
            async def go3(th, s):
                await self.gw.send_text(chat_id, f"{bold('Your certificate could not be generated right now.')}",
                                        ui.result_kb(th, ex, with_cert_btn=False))
            await self._with_theme(go3)

    async def _cert_bytes(self, ex: dict, r: dict) -> bytes:
        info = {"name": ex.get("name") or "Student", "username": ex.get("username") or "",
                "cls": "12th", "subject": ex["subject"], "chapter": ex["chapter"],
                "date": ui.fmt_date(ex.get("finished_at") or now()), "total": r["total"],
                "attempted": r["attempted"], "correct": r["correct"], "incorrect": r["incorrect"],
                "unattempted": r["unattempted"], "marks": r["marks"], "accuracy": r["accuracy"],
                "cert_id": "BNX-" + ex["_id"].upper()[:8]}
        return await asyncio.to_thread(self.render_cert, info)

    async def _hd_certificate(self, ctx: Ctx, eid: str) -> None:
        ex = await self.st.get_exam(eid)
        if not ex or ex["user_id"] != ctx.user_id or ex["status"] == "active" or not ex.get("result"):
            return await self.gw.answer_cb(ctx.cb_id, "Certificate not available.", True)
        await self.gw.answer_cb(ctx.cb_id, "Sending HD file…")
        data = await self._cert_bytes(ex, ex["result"])
        await self.gw.send_document_bytes(ctx.chat_id, data, f"BOTNEX_Certificate_{eid}.png", "📄 HD certificate")

    # ---------------------------------------------------------------- know answers
    async def _finished_exam(self, ctx: Ctx, eid: str):
        ex = await self.st.get_exam(eid)
        if not ex or ex["user_id"] != ctx.user_id:
            await self.gw.answer_cb(ctx.cb_id, "Not available.", True)
            return None
        if ex["status"] == "active":                          # answers must stay hidden during the exam
            await self.gw.answer_cb(ctx.cb_id, "Finish the exam first.", True)
            return None
        return ex

    async def _review(self, ctx: Ctx, eid: str, i: int) -> None:
        ex = await self._finished_exam(ctx, eid)
        if not ex:
            return
        await self.gw.answer_cb(ctx.cb_id)
        order = ex["order"][:ex["index"] + 1]
        i = max(0, min(i, len(order) - 1))
        q = self.qb.get(order[i])
        async def go(th, s):
            text = ui.review_text(th, ex, q, i, len(order), ex["answers"].get(q.id))
            kb = ui.review_kb(th, ex, i, len(order))
            if ctx.is_media:                                  # came from the certificate photo -> new message
                await self.gw.send_text(ctx.chat_id, text, kb)
            else:
                await self.gw.edit_text(ctx.chat_id, ctx.message_id, text, kb)
        await self._with_theme(go)

    async def _back_to_result(self, ctx: Ctx, eid: str) -> None:
        ex = await self._finished_exam(ctx, eid)
        if not ex:
            return
        await self.gw.answer_cb(ctx.cb_id)
        r = ex.get("result") or ui.compute_result(ex, self.qb)
        async def go(th, s):
            await self.gw.edit_text(ctx.chat_id, ctx.message_id, ui.result_text(th, ex, r, ex["status"]),
                                    ui.result_kb(th, ex), ctx.is_media)
        await self._with_theme(go)

    # ---------------------------------------------------------------- plain messages
    async def on_message(self, ctx: Ctx, inc: Incoming) -> None:
        async with self._lock(ctx.user_id):
            await self.st.upsert_user(ctx.user_id, self._name(ctx), ctx.username or "")
            if self.is_owner(ctx.user_id):
                if await self._owner_input(ctx, inc):
                    return
            async def go(th, s):
                kb = [[th.b("Main Menu", None, data="m:home", style="success")]]
                await self.gw.send_text(ctx.chat_id, f"{bold('Please use the buttons')} 👇\n"
                                        f"Send /start to open the menu.", kb)
            await self._with_theme(go)

    # ---------------------------------------------------------------- owner panel
    async def _admin(self, ctx: Ctx, p: list) -> None:
        if not self.is_owner(ctx.user_id):                    # authenticated id check, every time
            log.warning("Non-owner %s tried admin action", ctx.user_id)
            return await self.gw.answer_cb(ctx.cb_id, "Owner only.", True)
        a = p[0]
        s = await self.st.get_settings()
        if a == "cancel" or a == "home":
            await self.st.set_setting("awaiting_owner", "")
            s["awaiting_owner"] = ""
            await self.gw.answer_cb(ctx.cb_id)
            return await self._panel(ctx, s)
        if a == "prem":
            new = not s.get("premium_mode")
            await self.st.set_setting("premium_mode", new)
            note = ""
            if new and not s.get("premium_emoji") and not s.get("sticker_premium"):
                note = " (no premium emoji/sticker saved yet - set them first)"
            await self.gw.answer_cb(ctx.cb_id, f"Premium mode {'ON' if new else 'OFF'}{note}", bool(note))
            s["premium_mode"] = new
            return await self._panel(ctx, s)
        if a == "hid":
            new = not s.get("include_hidden")
            await self.st.set_setting("include_hidden", new)
            s["include_hidden"] = new
            await self.gw.answer_cb(ctx.cb_id, "Flagged questions " + ("SHOWN" if new else "HIDDEN"))
            return await self._panel(ctx, s)
        if a in ("stk", "pstk", "wel", "pemo"):
            kind = {"stk": "sticker_normal", "pstk": "sticker_premium", "wel": "welcome", "pemo": "emoji"}[a]
            await self.st.set_setting("awaiting_owner", kind)
            await self.gw.answer_cb(ctx.cb_id)
            return await self._owner_show(ctx, ui.ask_text(kind), ui.cancel_kb())
        if a == "wreset":
            await self.st.set_setting("welcome_file_id", "")
            await self.st.set_setting("welcome_kind", "")
            await self.gw.answer_cb(ctx.cb_id, "Welcome media reset to default")
            s["welcome_file_id"] = ""
            return await self._panel(ctx, s)
        if a == "stats":
            await self.gw.answer_cb(ctx.cb_id)
            return await self._stats(ctx)
        if a == "users":
            await self.gw.answer_cb(ctx.cb_id)
            return await self._users(ctx, int(p[1]) if len(p) > 1 else 0)
        await self.gw.answer_cb(ctx.cb_id)

    async def _owner_show(self, ctx: Ctx, text: str, kb: list) -> None:
        await self.gw.edit_text(ctx.chat_id, ctx.message_id, text, kb, ctx.is_media)

    async def _panel(self, ctx: Ctx, s: dict) -> None:
        th = Theme.normal()                                    # panel always uses plain theme (always works)
        await self._owner_show(ctx, ui.panel_text(th, s), ui.panel_kb(th, s))

    async def _stats(self, ctx: Ctx) -> None:
        th = Theme.normal()
        users = await self.st.count_users()
        active = await self.st.count_active_users(now() - 86400)
        total = await self.st.count_exams()
        completed = await self.st.count_exams(status="completed")
        ended = await self.st.count_exams(status="ended")
        lines = [f"{bold('STATS')}\n{LINE}",
                 f"👥 {bold('Registered users')}: {users}", f"🟢 {bold('Active (24h)')}: {active}",
                 f"📝 {bold('Exams started')}: {total}", f"🏁 {bold('Finished')}: {completed + ended} "
                 f"(auto {completed} / ended early {ended})", LINE, bold("Subject-wise (finished)")]
        for sub in self.qb.subject_list(CLS):
            n = (await self.st.count_exams(subject_slug=sub.slug, status="completed") +
                 await self.st.count_exams(subject_slug=sub.slug, status="ended"))
            lines.append(f"• {esc(sub.name)}: {n}")
        done = (await self.st.list_exams(status="completed")) + (await self.st.list_exams(status="ended"))
        top = Counter(f"{e['subject']} - {e['chapter']}" for e in done).most_common(8)
        lines += [LINE, bold("Top chapters")]
        lines += [f"• {esc(k)}: {v}" for k, v in top] or ["• no exams yet"]
        await self._owner_show(ctx, "\n".join(lines), ui.back_panel_kb(th))

    async def _users(self, ctx: Ctx, page: int) -> None:
        th = Theme.normal()
        total = await self.st.count_users()
        pages = max(1, (total + ui.PER_PAGE - 1) // ui.PER_PAGE)
        page = max(0, min(page, pages - 1))
        rows = await self.st.list_users(page * ui.PER_PAGE, ui.PER_PAGE)
        lines = [f"{bold('USERS')}  ({total})  •  {page + 1}/{pages}\n{LINE}"]
        for i, u in enumerate(rows, page * ui.PER_PAGE + 1):
            uname = f"@{esc(u['username'])}" if u.get("username") else "—"
            lines.append(f"{i}. {esc(u.get('first_name', ''))} {uname}\n   🆔 <code>{u['_id']}</code> • "
                         f"📝 {u.get('attempts', 0)} • 🕒 {ui.ago(u.get('last_active'))}")
        nav = []
        if page > 0:
            nav.append(Btn(text="◀️", data=f"ad:users:{page - 1}", style="primary"))
        if page < pages - 1:
            nav.append(Btn(text="▶️", data=f"ad:users:{page + 1}", style="primary"))
        kb = ([nav] if nav else []) + ui.back_panel_kb(th)
        await self._owner_show(ctx, "\n".join(lines), kb)

    async def _owner_input(self, ctx: Ctx, inc: Incoming) -> bool:
        """Owner replies to a panel request (sticker / photo / premium emoji). Returns True if handled."""
        s = await self.st.get_settings()
        kind = s.get("awaiting_owner")
        if not kind:
            return False
        ok, msg = False, ""
        if kind in ("sticker_normal", "sticker_premium") and inc.kind == "sticker" and inc.file_id:
            await self.st.set_setting(kind, inc.file_id)
            ok, msg = True, "✅ Sticker saved."
        elif kind == "welcome" and inc.kind in ("photo", "animation") and inc.file_id:
            await self.st.set_setting("welcome_file_id", inc.file_id)
            await self.st.set_setting("welcome_kind", inc.kind)
            ok, msg = True, "✅ Welcome media saved."
        elif kind == "emoji" and inc.emoji_ids:
            ids = {slot: cid for (slot, _), cid in zip(SLOTS, inc.emoji_ids)}
            cur = dict(s.get("premium_emoji") or {})
            cur.update(ids)
            await self.st.set_setting("premium_emoji", cur)
            ok, msg = True, f"✅ {len(ids)} premium emoji saved."
        else:
            msg = "That is not what I asked for. Send the requested item or press Cancel."
        if ok:
            await self.st.set_setting("awaiting_owner", "")
        s = await self.st.get_settings()
        th = Theme.normal()
        kb = ui.panel_kb(th, s) if ok else ui.cancel_kb()
        await self.gw.send_text(ctx.chat_id, msg + ("\n\n" + ui.panel_text(th, s) if ok else ""), kb)
        return True
