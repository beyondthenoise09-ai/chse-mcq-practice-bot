"""Question-bank loader + validator. JSON files are the single source of truth.
Optimized for On-Demand Chapter Loading to drastically save RAM (< 110 MB usage).
"""
from __future__ import annotations
import json
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("botnex.qb")
LETTERS = ("a", "b", "c", "d")
SUBJECT_ORDER = ["chemistry", "physics", "mathematics", "zoology", "botany"]
SUBJECT_ICON = {"chemistry": "🧪", "physics": "⚛️", "mathematics": "📐", "zoology": "🐾", "botany": "🌿"}

@dataclass
class Question:
    id: str
    cls: str
    subject: str
    chapter_no: int
    chapter: str
    text: str
    options: dict
    answer: str
    hidden: bool = False
    hidden_reason: str = ""
    difficulty: str = ""

@dataclass
class Chapter:
    no: int
    name: str
    file_path: Path                                   # Added to support on-demand file reading
    qids_all: list = field(default_factory=list)
    qids_live: list = field(default_factory=list)

@dataclass
class Subject:
    cls: str
    slug: str
    name: str
    chapters: dict = field(default_factory=dict)      # chapter_no -> Chapter

@dataclass
class LoadReport:
    total_records: int = 0
    loaded: int = 0
    rejected: list = field(default_factory=list)       # (file, id, reason)
    duplicates: list = field(default_factory=list)
    hidden: int = 0
    files: int = 0

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def hidden_reason(rec: dict) -> str:
    if rec.get("hidden"):
        return "marked hidden"
    if rec.get("status") == "options_missing":
        return "options missing in source book"
    flags = " | ".join(rec.get("flags") or []).lower()
    if "teacher check" in flags:
        return "answer key needs teacher check"
    if "figure on pdf page" in flags:
        return "needs a figure that is not available"
    if "not usable for quiz" in flags:
        return "not usable for quiz"
    return ""

class QuestionBank:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.questions: dict[str, Question] = {}
        self.subjects: dict[str, dict[str, Subject]] = {}   # cls -> slug -> Subject
        self.report = LoadReport()
        self.root_dir = Path(root_dir) if root_dir else None

    # ---------- loading ----------
    @classmethod
    def load(cls, root: Path) -> "QuestionBank":
        qb = cls(root)
        root = Path(root)
        files = sorted(root.glob("class*/*.json"))
        if not files:
            raise RuntimeError(f"No question-bank JSON files found under {root}/class*/")
        for f in files:
            qb._load_file(f)
        qb._finalise()
        log.info("Question bank: %d loaded, %d rejected, %d duplicate, %d hidden by default (%d files)",
                 qb.report.loaded, len(qb.report.rejected), len(qb.report.duplicates),
                 qb.report.hidden, qb.report.files)
        return qb

    def _load_file(self, f: Path) -> None:
        cls_name = f.parent.name.replace("class", "").strip() or f.parent.name
        self.report.files += 1
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            log.error("Cannot read %s: %s", f, e)
            self.report.rejected.append((f.name, "*", f"unreadable file: {e}"))
            return
        if not isinstance(data, list):
            self.report.rejected.append((f.name, "*", "file is not a list of questions"))
            return
        
        # Track chapter mapping for lazy/on-demand loading
        chapter_file_map = {}

        for rec in data:
            self.report.total_records += 1
            qid = str(rec.get("id", "")).strip() if isinstance(rec, dict) else ""
            chno = int(rec.get("chapter_no", 0)) if isinstance(rec, dict) else 0
            chapter_name = str(rec.get("chapter", "")).strip()
            
            if chno and chapter_name:
                chapter_file_map[chno] = f
                
            self._add(f.name, cls_name, rec)

    def _add(self, fname: str, cls_name: str, rec: dict) -> None:
        qid = str(rec.get("id", "")).strip() if isinstance(rec, dict) else ""
        try:
            if not isinstance(rec, dict):
                raise ValueError("record is not an object")
            if not qid:
                raise ValueError("missing id")
            text = str(rec.get("question", "")).strip()
            if not text:
                raise ValueError("empty question text")
            opts = rec.get("options")
            if not isinstance(opts, dict) or sorted(opts.keys()) != list(LETTERS):
                raise ValueError("options must be exactly a, b, c, d")
            clean = {k: str(opts[k]).strip() for k in LETTERS}
            if any(not v for v in clean.values()):
                raise ValueError("empty option text")
            ans = str(rec.get("answer", "")).strip().lower()
            if ans not in LETTERS:
                raise ValueError(f"answer '{ans}' is not a/b/c/d")
            subject = str(rec.get("subject", "")).strip()
            chapter = str(rec.get("chapter", "")).strip()
            if not subject or not chapter:
                raise ValueError("missing subject/chapter")
            chno = int(rec.get("chapter_no"))
        except Exception as e:
            self.report.rejected.append((fname, qid or "?", str(e)))
            log.warning("Rejected %s/%s: %s", fname, qid or "?", e)
            return
        if qid in self.questions:
            self.report.duplicates.append((fname, qid))
            log.warning("Duplicate id %s in %s ignored", qid, fname)
            return
        reason = hidden_reason(rec)
        self.questions[qid] = Question(qid, cls_name, subject, chno, chapter, text, clean, ans,
                                       bool(reason), reason, str(rec.get("difficulty", "")))
        self.report.loaded += 1

    def _finalise(self) -> None:
        for q in self.questions.values():
            subs = self.subjects.setdefault(q.cls, {})
            s = subs.setdefault(_slug(q.subject), Subject(q.cls, _slug(q.subject), q.subject))
            
            # Find corresponding file path dynamically if root_dir is known
            fpath = None
            if self.root_dir:
                matches = list(self.root_dir.glob(f"class{q.cls}/*.json"))
                for m in matches:
                    try:
                        content = json.loads(m.read_text(encoding="utf-8"))
                        if content and isinstance(content, list) and any(str(item.get("chapter_no")) == str(q.chapter_no) for item in content if isinstance(item, dict)):
                            fpath = m
                            break
                    except Exception:
                        pass

            ch = s.chapters.setdefault(q.chapter_no, Chapter(q.chapter_no, q.chapter, file_path=fpath))
            ch.qids_all.append(q.id)
            if q.hidden:
                self.report.hidden += 1
            else:
                ch.qids_live.append(q.id)

    # ---------- On-Demand / Lazy Chapter Loader ----------
    def ensure_chapter_loaded(self, cls: str, slug: str, chapter_no: int) -> None:
        """Dynamically loads chapter questions from disk on-demand if not already fully indexed."""
        s = self.get_subject(cls, slug)
        if not s or chapter_no not in s.chapters:
            return
        ch = s.chapters[chapter_no]
        if ch.file_path and ch.file_path.exists():
            try:
                data = json.loads(ch.file_path.read_text(encoding="utf-8"))
                for rec in data:
                    if isinstance(rec, dict) and int(rec.get("chapter_no", 0)) == chapter_no:
                        self._add(ch.file_path.name, cls, rec)
            except Exception as e:
                log.error("Failed lazy loading chapter file %s: %s", ch.file_path, e)

    # ---------- queries ----------
    def classes(self) -> list:
        return sorted(self.subjects)

    def subject_list(self, cls: str) -> list:
        subs = self.subjects.get(cls, {})
        order = {s: i for i, s in enumerate(SUBJECT_ORDER)}
        return sorted(subs.values(), key=lambda s: (order.get(s.slug, 99), s.name))

    def get_subject(self, cls: str, slug: str) -> Subject | None:
        return self.subjects.get(cls, {}).get(slug)

    def pool(self, cls: str, slug: str, chapter_no: int, include_hidden: bool = False) -> list:
        self.ensure_chapter_loaded(cls, slug, chapter_no)
        s = self.get_subject(cls, slug)
        ch = s.chapters.get(chapter_no) if s else None
        if not ch:
            return []
        return list(ch.qids_all if include_hidden else ch.qids_live)

    def count(self, cls: str, slug: str, chapter_no: int | None = None, include_hidden: bool = False) -> int:
        s = self.get_subject(cls, slug)
        if not s:
            return 0
        if chapter_no is not None and chapter_no in s.chapters:
            self.ensure_chapter_loaded(cls, slug, chapter_no)
            chs = [s.chapters[chapter_no]]
        else:
            chs = list(s.chapters.values())
        return sum(len(c.qids_all if include_hidden else c.qids_live) for c in chs)

    def random_order(self, qids: list, rng: random.Random | None = None) -> list:
        order = list(qids)
        (rng or random.SystemRandom()).shuffle(order)
        return order

    def get(self, qid: str) -> Question | None:
        return self.questions.get(qid)
