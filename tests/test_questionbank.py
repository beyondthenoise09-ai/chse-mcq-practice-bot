import json, tempfile, unittest
from pathlib import Path
from botnex_quiz.questionbank import QuestionBank
from .helpers import ROOT, real_qb

def rec(i, **kw):
    d = {"id": i, "subject": "Physics", "class": 12, "chapter_no": 1, "chapter": "Ch", "question": "Q?",
         "options": {"a": "1", "b": "2", "c": "3", "d": "4"}, "answer": "b", "flags": []}
    d.update(kw); return d

def bank_from(records, name="physics.json"):
    td = tempfile.mkdtemp(); (Path(td) / "class12").mkdir()
    (Path(td) / "class12" / name).write_text(json.dumps(records), encoding="utf-8")
    return QuestionBank.load(Path(td))

class RealBank(unittest.TestCase):
    def test_counts_and_subjects(self):
        qb = real_qb()
        self.assertEqual(qb.report.total_records, 2044)
        self.assertEqual(qb.report.loaded + len(qb.report.rejected) + len(qb.report.duplicates), 2044)
        self.assertEqual(len(qb.report.rejected), 3)              # 3 questions have no options in the source book
        self.assertEqual(qb.report.hidden, 33)                    # 14 teacher-check + 19 figure questions
        names = [s.name for s in qb.subject_list("12")]
        self.assertEqual(names, ["Chemistry", "Physics", "Mathematics", "Zoology", "Botany"])
    def test_every_loaded_question_valid(self):
        for q in real_qb().questions.values():
            self.assertIn(q.answer, "abcd"); self.assertEqual(sorted(q.options), list("abcd"))
            self.assertTrue(all(q.options.values()))
    def test_hidden_not_in_live_pool(self):
        qb = real_qb()
        for s in qb.subject_list("12"):
            for ch in s.chapters.values():
                for qid in ch.qids_live: self.assertFalse(qb.get(qid).hidden)
                self.assertEqual(len(ch.qids_all) - len(ch.qids_live), sum(1 for x in ch.qids_all if qb.get(x).hidden))

class Validation(unittest.TestCase):
    def test_rejects_malformed_never_silently(self):
        qb = bank_from([rec("ok"), rec("noans", answer="e"), rec("noopt", options={"a": "1"}),
                        rec("empty", question=" "), rec("noid", id=""), {"junk": 1},
                        rec("blankopt", options={"a": "1", "b": "", "c": "3", "d": "4"}),
                        rec("nochap", chapter="")])
        self.assertEqual(qb.report.loaded, 1)
        self.assertEqual(len(qb.report.rejected), 7)
    def test_duplicates_detected(self):
        qb = bank_from([rec("x"), rec("x")])
        self.assertEqual(qb.report.loaded, 1); self.assertEqual(len(qb.report.duplicates), 1)
    def test_flag_rules(self):
        qb = bank_from([rec("t", flags=["x - TEACHER CHECK"]), rec("f", flags=["figure on PDF page 5"]),
                        rec("m", status="options_missing"), rec("n", flags=["verify only"]), rec("h", hidden=True)])
        hid = {q.id for q in qb.questions.values() if q.hidden}
        self.assertEqual(hid, {"t", "f", "m", "h"})               # plain "verify" notes do NOT hide a question
        self.assertFalse(qb.get("n").hidden)
    def test_unreadable_file_does_not_crash(self):
        td = tempfile.mkdtemp(); (Path(td) / "class12").mkdir()
        (Path(td) / "class12" / "bad.json").write_text("{not json", encoding="utf-8")
        (Path(td) / "class12" / "ok.json").write_text(json.dumps([rec("a")]), encoding="utf-8")
        qb = QuestionBank.load(Path(td)); self.assertEqual(qb.report.loaded, 1)
    def test_new_class_folder_needs_no_code(self):
        td = tempfile.mkdtemp()
        for c in ("class11", "class12"):
            (Path(td) / c).mkdir(); (Path(td) / c / "physics.json").write_text(json.dumps([rec(c + "1")]))
        qb = QuestionBank.load(Path(td)); self.assertEqual(qb.classes(), ["11", "12"])
