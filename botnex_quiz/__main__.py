"""Entry point:  python -m botnex_quiz"""
from __future__ import annotations
import asyncio
import logging
from .certificate import render_certificate
from .config import load_config
from .flow import Controller
from .questionbank import QuestionBank
from .storage import MemoryStorage, MongoStorage

async def main() -> None:
    cfg = load_config()
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("botnex")
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from .aio_app import build_dispatcher
    from .aio_gateway import AiogramGateway

    qb = QuestionBank.load(cfg.questionbank_dir)
    if qb.report.rejected:
        log.warning("%d question records were rejected (see log above)", len(qb.report.rejected))
    if cfg.mongo_uri:
        storage = MongoStorage(cfg.mongo_uri, cfg.mongo_db_name)
    else:
        log.warning("MONGO_DB_URI not set -> using MEMORY storage (data is lost on restart!)")
        storage = MemoryStorage()
    await storage.init()
    if not cfg.owner_id:
        log.warning("OWNER_ID not set -> Owner Panel is disabled")

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    ctrl = Controller(cfg, qb, storage, AiogramGateway(bot), render_certificate)
    dp = build_dispatcher(ctrl)
    me = await bot.get_me()
    log.info("BOTNEX Quiz started as @%s", me.username)
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
