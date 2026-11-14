"""All user-facing texts and keyboards (pure functions -> easy to test)."""
from __future__ import annotations
import time
from datetime import datetime, timedelta, timezone
from .gateway import Btn
from .styling import bold, bold_italic, btn as btn_font, esc, LINE, script
from .theme import Theme, SLOTS
from .questionbank import SUBJECT_ICON

IST = timezone(timedelta(hours=5, minutes=30))
PER_PAGE = 8

# ------------------------------------------------------------------ intro / welcome
def intro_frames(t: Theme, delay_dots: bool = True) -> list:
    sp, bolt, hour, dia = t.e("sparkle"), "⚡", "⏳", t.e("diamond")
    return [
        f"{sp} {bold('Welcome Buddy')} 👋 {sp}",
        f"{bolt} {bold_italic('Bot is Alive Baby')} {bolt}\n{LINE}",
        f"{hour} {bold('Wait')} • {bold('Bot Starting')}\n▰▱▱▱▱▱▱▱▱▱ 10%",
        f"{hour} {bold('Wait')} • {bold('Bot Starting')}\n▰▰▰▰▱▱▱▱▱▱ 45%",
        f"{hour} {bold('Wait')} • {bold('Bot Starting')}\n▰▰▰▰▰▰▰▰▱▱ 85%",
        f"{sp} {bold('Ready')} {sp}\n▰▰▰▰▰▰▰▰▰▰ 100%",
        f"{dia} {bold('Powered by')} {bold('BOTNEX')} {bold('by Chandan Nayak')} {dia}",
    ]

def welcome_caption(t: Theme, name: str, bot_name: str) -> str:
    return (
        f"{t.e('cap')} {bold('Welcome')}, {esc(name)}!\n"
        f"{LINE}\n"
        f"{t.e('sparkle')} {bold('Welcome to ' + bot_name)}\n"
        f"{bold_italic('Your smart learning companion for Class 12.')}\n\n"
        f"Practice chapter-wise questions, test your preparation, "
        f"check your result and see exactly where you went wrong.\n\n"
        f"{t.e('book')} {bold('Learn better. Practice smarter. Score higher.')}\n"
        f"{LINE}\n"
        f"{t.e('diamond')} {bold('Powered by BOTNEX by Chandan Nayak')}"
    )

def welcome_kb(t: Theme, cfg, is_owner: bool) -> list:
    rows = [
        [Btn(text="🔒 " + btn_font("Class 11th") + " • " + btn_font("Soon"), data="m:c11", style="danger")],
        [t.b("Class 12th", "cap", data="m:c12", style="success")],
        [t.b("Owner", None, url=cfg.owner_url, style="success"),
         t.b("Support", None, url=cfg.support_link, style="primary")],
    ]
    if is_owner:
        rows.append([t.b("Owner Panel", "diamond", data="ad:home", style="primary")])
    return rows

# ------------------------------------------------------------------ navigation
def class_menu_text(t: Theme) -> str:
    return (f"{t.e('cap')} {bold('Class 12th')}\n{LINE}\n"
            f"{t.e('book')} {bold('Choose your subject')}\n{LINE}")

def subjects_kb(t: Theme, subjects: list, counts: dict) -> list:
    rows, row = [], []
    for s in subjects:
        icon = SUBJECT_ICON.get(s.slug, "📘")
        b = Btn(text=f"{icon} {btn_font(s.name)} • {counts.get(s.slug, 0)}", data=f"sb:{s.slug}:0",
                style="primary")
        row.append(b)
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([t.b("Main Menu", None, data="m:home", style="danger")])
    return rows

def chapters_text(t: Theme, subject, page: int, pages: int) -> str:
    icon = SUBJECT_ICON.get(subject.slug, "📘")
    return (f"{icon} {bold(subject.name.upper())}  •  {bold('Class 12')}\n{LINE}\n"
            f"{t.e('book')} {bold('Choose a chapter')}  ({page + 1}/{pages})\n{LINE}")

def chapters_kb(t: Theme, subject, live_counts: dict, page: int) -> tuple:
    chs = [c for c in sorted(subject.chapters.values(), key=lambda c: c.no) if live_counts.get(c.no, 0) > 0]
    pages = max(1, (len(chs) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))
    rows = []
    for c in chs[page * PER_PAGE:(page + 1) * PER_PAGE]:
        name = c.name if len(c.name) <= 30 else c.name[:29] + "…"
        rows.append([Btn(text=f"{c.no:02d} • {name} ({live_counts[c.no]})", data=f"cp:{subject.slug}:{c.no}",
                         style="primary" if c.no % 2 else "success")])
    nav = []
    if page > 0:
        nav.append(Btn(text="◀️ " + btn_font("Prev"), data=f"sb:{subject.slug}:{page - 1}", style="primary"))
    if page < pages - 1:
        nav.append(Btn(text=btn_font("Next") + " ▶️", data=f"sb:{subject.slug}:{page + 1}", style="primary"))
    if nav:
        rows.append(nav)
    rows.append([t.b("Back", None, data="m:c12", style="primary"), t.b("Main Menu", None, data="m:home", style="danger")])
    return rows, page, pages

# ------------------------------------------------------------------ quiz
def question_text(t: Theme, ex: dict, q, number: int, total: int, chosen: str | None) -> str:
    icon = SUBJECT_ICON.get(ex["subject_slug"], "📘")
    opts = "\n\n".join(f"{bold(L.upper())})  {esc(q.options[L])}" for L in "abcd")
    s = (f"{LINE}\n{icon} {bold('CLASS 12')} | {bold(ex['subject'].upper())}\n"
         f"{t.e('book')} {bold('Chapter')}: {esc(ex['chapter'])}\n"
         f"{bold('Question')} {number:02d}/{total}\n{LINE}\n\n"
         f"{esc(q.text)}\n\n{LINE}\n{opts}\n{LINE}")
    if chosen:
        s += f"\n{t.e('check')} {bold('Your answer')}: {bold(chosen.upper())} {bold_italic('(locked)')}"
    return s

def question_kb(t: Theme, eid: str, idx: int, chosen: str | None) -> list:
    if not chosen:
        row = [Btn(text=L.upper(), data=f"a:{eid}:{idx}:{L}", style="primary") for L in "abcd"]
        return [row, [t.b("End Exam", "flag", data=f"e:{eid}:{idx}", style="danger")]]
    return [[Btn(text=f"✅ {chosen.upper()}", data="x:0", style="success")],
            [t.b("Next Question", "next", data=f"n:{eid}:{idx}", style="success"),
             t.b("End Exam", "flag", data=f"e:{eid}:{idx}", style="danger")]]

def locked_kb(chosen: str | None) -> list | None:
    if not chosen:
        return None
    return [[Btn(text=f"✅ {chosen.upper()}", data="x:0", style="success")]]

# ------------------------------------------------------------------ result
def completed_text(t: Theme) -> str:
    return (f"{t.e('trophy')} {bold('Your exam is finished!')}\n"
            f"{bold_italic('You have attempted all the questions available in this chapter.')}")

def _pct(x: float) -> str:
    return f"{x:.0f}%" if abs(x - round(x)) < 1e-9 else f"{x:.1f}%"

def compute_result(ex: dict, qb) -> dict:
    shown = ex["index"] + 1
    order = ex["order"][:shown]
    attempted = correct = 0
    for qid in order:
        a = ex["answers"].get(qid)
        if a:
            attempted += 1
            q = qb.get(qid)
            if q and a == q.answer:
                correct += 1
    return {"total": shown, "attempted": attempted, "correct": correct, "incorrect": attempted - correct,
            "unattempted": shown - attempted, "marks": correct,
            "accuracy": (100.0 * correct / attempted) if attempted else 0.0}

def result_text(t: Theme, ex: dict, r: dict, status: str) -> str:
    who = esc(ex.get("name") or "Student")
    if ex.get("username"):
        who += f" (@{esc(ex['username'])})"
    head = ("EXAMINATION COMPLETED" if status == "completed" else "EXAMINATION ENDED")
    msg = ("Congratulations! You have completed every question of this chapter."
           if status == "completed" else "Well done! Here is your result for the questions you attempted.")
    return (f"{LINE}\n{t.e('trophy')} {bold(head)}\n\n{t.e('sparkle')} {bold_italic(msg)}\n\n"
            f"{t.e('book')} {bold('Subject')}: {esc(ex['subject'])}\n"
            f"{t.e('cap')} {bold('Chapter')}: {esc(ex['chapter'])}\n"
            f"👤 {bold('Student')}: {who}\n\n"
            f"📝 {bold('Total Questions')}: {r['total']}\n"
            f"✍️ {bold('Attempted')}: {r['attempted']}\n"
            f"{t.e('check')} {bold('Correct Answers')}: {r['correct']}\n"
            f"{t.e('cross')} {bold('Incorrect Answers')}: {r['incorrect']}\n"
            f"⚪ {bold('Unattempted')}: {r['unattempted']}\n\n"
            f"{t.e('target')} {bold('Marks')}: {r['marks']}/{r['total']}\n"
            f"📊 {bold('Accuracy')}: {_pct(r['accuracy'])}\n{LINE}\n"
            f"{t.e('diamond')} {bold('Powered by BOTNEX')}")

def result_kb(t: Theme, ex: dict, with_cert_btn: bool = True) -> list:
    rows = [[t.b("Know Answers", "book", data=f"ka:{ex['_id']}:0", style="success")]]
    if with_cert_btn:
        rows[0].append(t.b("HD Certificate", "trophy", data=f"hd:{ex['_id']}", style="primary"))
    rows.append([t.b("Try Again", "fire", data=f"ag:{ex['subject_slug']}:{ex['chapter_no']}", style="primary"),
                 t.b("Main Menu", None, data="m:home", style="danger")])
    return rows

def cert_caption(t: Theme, ex: dict, r: dict) -> str:
    return (f"{t.e('trophy')} {bold('Your Certificate')}\n"
            f"{esc(ex['subject'])} • {esc(ex['chapter'])}\n"
            f"{t.e('target')} {r['marks']}/{r['total']}  •  {_pct(r['accuracy'])}")

# ------------------------------------------------------------------ know answers
def review_text(t: Theme, ex: dict, q, i: int, n: int, chosen: str | None) -> str:
    if not chosen:
        status = f"⚪ {bold('Not Attempted')}"
    elif chosen == q.answer:
        status = f"{t.e('check')} {bold('Correct')}"
    else:
        status = f"{t.e('cross')} {bold('Incorrect')}"
    your = f"{chosen.upper()}) {esc(q.options[chosen])}" if chosen else "—"
    return (f"{LINE}\n{t.e('book')} {bold('Know Answers')}  •  {bold('Question')} {i + 1:02d}/{n}\n{LINE}\n\n"
            f"{esc(q.text)}\n\n"
            f"{bold('Your Answer')}: {your}\n"
            f"{bold('Correct Answer')}: {q.answer.upper()}) {esc(q.options[q.answer])}\n\n"
            f"{status}\n{LINE}")

def review_kb(t: Theme, ex: dict, i: int, n: int) -> list:
    eid = ex["_id"]
    nav = []
    if i > 0:
        nav.append(Btn(text="◀️ " + btn_font("Previous"), data=f"ka:{eid}:{i - 1}", style="primary"))
    if i < n - 1:
        nav.append(Btn(text=btn_font("Next") + " ▶️", data=f"ka:{eid}:{i + 1}", style="success"))
    rows = [nav] if nav else []
    rows.append([t.b("Back to Result", "trophy", data=f"rs:{eid}", style="danger")])
    return rows

# ------------------------------------------------------------------ owner panel
def panel_text(t: Theme, s: dict) -> str:
    return (f"{t.e('diamond')} {bold('OWNER PANEL')}\n{LINE}\n"
            f"💎 {bold('Premium mode')}: {bold('ON' if s.get('premium_mode') else 'OFF')}\n"
            f"🎭 {bold('Normal sticker')}: {'set' if s.get('sticker_normal') else 'default'}\n"
            f"👑 {bold('Premium sticker')}: {'set' if s.get('sticker_premium') else 'not set'}\n"
            f"✨ {bold('Premium emojis set')}: {len(s.get('premium_emoji') or {})}/{len(SLOTS)}\n"
            f"🖼 {bold('Welcome media')}: {'custom' if s.get('welcome_file_id') else 'default'}\n"
            f"🧩 {bold('Flagged questions')}: {bold('SHOWN' if s.get('include_hidden') else 'hidden')}\n{LINE}")

def panel_kb(t: Theme, s: dict) -> list:
    return [
        [Btn(text="📊 " + btn_font("Stats"), data="ad:stats", style="primary"),
         Btn(text="👥 " + btn_font("Users"), data="ad:users:0", style="primary")],
        [Btn(text=("💎 " + btn_font("Premium") + ": " + ("ON ✅" if s.get("premium_mode") else "OFF ⭕")),
             data="ad:prem", style="success" if s.get("premium_mode") else "danger")],
        [Btn(text="🎭 " + btn_font("Sticker"), data="ad:stk", style="primary"),
         Btn(text="👑 " + btn_font("Premium Sticker"), data="ad:pstk", style="primary")],
        [Btn(text="✨ " + btn_font("Premium Emoji"), data="ad:pemo", style="primary"),
         Btn(text="🖼 " + btn_font("Welcome Photo"), data="ad:wel", style="primary")],
        [Btn(text="🧩 " + btn_font("Flagged Questions") + ": " + ("SHOWN" if s.get("include_hidden") else "HIDDEN"),
             data="ad:hid", style="primary")],
        [Btn(text="♻️ " + btn_font("Reset Welcome"), data="ad:wreset", style="danger"),
         t.b("Main Menu", None, data="m:home", style="danger")],
    ]

def ask_text(kind: str) -> str:
    if kind == "sticker_normal":
        return f"🎭 {bold('Send the new normal sticker now.')}"
    if kind == "sticker_premium":
        return f"👑 {bold('Send the new premium sticker now.')}"
    if kind == "welcome":
        return f"🖼 {bold('Send the new welcome photo or GIF/animation now.')}"
    if kind == "emoji":
        order = "  ".join(f"{i + 1}.{e}" for i, (_, e) in enumerate(SLOTS))
        return (f"✨ {bold('Send ONE message containing premium (custom) emojis in this order:')}\n\n{order}\n\n"
                f"Only the first {len(SLOTS)} custom emojis are used. (Needs a Telegram Premium account.)")
    return ""

def cancel_kb() -> list:
    return [[Btn(text="✖ " + btn_font("Cancel"), data="ad:cancel", style="danger")]]

def back_panel_kb(t: Theme) -> list:
    return [[Btn(text="◀️ " + btn_font("Owner Panel"), data="ad:home", style="primary")]]

def ago(ts: int | None) -> str:
    if not ts:
        return "never"
    d = int(time.time()) - int(ts)
    if d < 90: return "just now"
    if d < 5400: return f"{d // 60}m ago"
    if d < 172800: return f"{d // 3600}h ago"
    return f"{d // 86400}d ago"

def fmt_date(ts: int | None) -> str:
    return datetime.fromtimestamp(ts or time.time(), IST).strftime("%d %b %Y")
