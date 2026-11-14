"""Configuration. Secrets only from environment variables (.env supported)."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _load_dotenv() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_id: int                     # numeric Telegram ID of the owner (env OWNER_ID)
    owner_username: str = "lll_SOLAC_lll"
    support_link: str = "https://t.me/BOT_NEX_A"
    bot_display_name: str = "BOTNEX Quiz Academy"
    mongo_uri: str = ""
    mongo_db_name: str = "botnex_quiz"
    default_sticker_id: str = ("CAACAgUAAxkBAAEwh6Jq9vfQQfGNh_eAiSc3Ugf2-1CtCwAC"
                               "yxEAAsxu-VZ0soGVipO6tz0E")
    questionbank_dir: Path = ROOT / "questionbank"
    assets_dir: Path = ROOT / "assets"
    log_level: str = "INFO"

    @property
    def owner_url(self) -> str:
        return f"https://t.me/{self.owner_username.lstrip('@')}"

def load_config(require_token: bool = True) -> Config:
    _load_dotenv()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if require_token and not token:
        raise SystemExit("BOT_TOKEN is not set. Put it in the environment or .env file.")
    try:
        owner_id = int(os.environ.get("OWNER_ID", "0").strip() or 0)
    except ValueError:
        raise SystemExit("OWNER_ID must be a number (your numeric Telegram user id).")
    kw = {}
    for env, field in (("OWNER_USERNAME", "owner_username"), ("SUPPORT_LINK", "support_link"),
                       ("BOT_DISPLAY_NAME", "bot_display_name"), ("MONGO_DB_URI", "mongo_uri"),
                       ("MONGO_DB_NAME", "mongo_db_name"), ("STICKER_ID", "default_sticker_id"),
                       ("LOG_LEVEL", "log_level")):
        v = os.environ.get(env, "").strip()
        if v:
            kw[field] = v
    return Config(bot_token=token, owner_id=owner_id, **kw)
