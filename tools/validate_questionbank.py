"""Check the question bank before deploying:  python tools/validate_questionbank.py"""
import logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from botnex_quiz.questionbank import QuestionBank

logging.basicConfig(level=logging.WARNING)
qb = QuestionBank.load(Path(__file__).resolve().parent.parent / "questionbank")
r = qb.report
print(f"files: {r.files}  records: {r.total_records}  loaded: {r.loaded}  rejected: {len(r.rejected)}  "
      f"duplicates: {len(r.duplicates)}  hidden-by-default: {r.hidden}")
for f, i, why in r.rejected: print(f"  REJECTED {f} {i}: {why}")
for f, i in r.duplicates: print(f"  DUPLICATE {f} {i}")
for cls in qb.classes():
    print(f"Class {cls}")
    for s in qb.subject_list(cls):
        live = sum(len(c.qids_live) for c in s.chapters.values()); allq = sum(len(c.qids_all) for c in s.chapters.values())
        print(f"  {s.name:12s} chapters={len(s.chapters):2d} questions={allq:4d} live={live:4d}")
