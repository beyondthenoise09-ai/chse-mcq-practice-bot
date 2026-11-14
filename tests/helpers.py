import asyncio
from pathlib import Path
from botnex_quiz.config import Config
from botnex_quiz.flow import Controller
from botnex_quiz.questionbank import QuestionBank
from botnex_quiz.storage import MemoryStorage
from .fakes import FakeGateway, Sim, User

ROOT = Path(__file__).resolve().parent.parent
OWNER_ID = 999001

def make_cfg():
    return Config(bot_token="TEST", owner_id=OWNER_ID, assets_dir=ROOT / "assets",
                  questionbank_dir=ROOT / "questionbank")

_QB = None
def real_qb():
    global _QB
    if _QB is None:
        _QB = QuestionBank.load(ROOT / "questionbank")
    return _QB

def fake_cert(info):
    return b"\x89PNG\r\n\x1a\n" + repr(sorted(info.items())).encode()

def make_env(storage=None, qb=None, gw=None):
    gw = gw or FakeGateway()
    storage = storage or MemoryStorage()
    ctrl = Controller(make_cfg(), qb or real_qb(), storage, gw, fake_cert, intro_delay=0)
    return ctrl, gw, storage, Sim(ctrl, gw)

def answer_key(ctrl, qid):
    return ctrl.qb.get(qid).answer

def wrong_letter(ctrl, qid):
    return "a" if ctrl.qb.get(qid).answer != "a" else "b"
