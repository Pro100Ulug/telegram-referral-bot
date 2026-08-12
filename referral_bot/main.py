import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from referral_bot.config import BOT_TOKEN, PROXY_URL
from referral_bot.database import init_db
from referral_bot.handlers import start, profile, referral, wallet, withdrawal, admin, help, callbacks
from referral_bot.middlewares import AutoRegisterMiddleware, CallbackLoggerMiddleware

log = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("TOKEN loaded: %s", bool(BOT_TOKEN))

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set. Create .env with BOT_TOKEN=<your_token>")

    init_db()
    logger.info("Database initialized")

    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(AutoRegisterMiddleware())
    dp.callback_query.middleware(CallbackLoggerMiddleware())

    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(referral.router)
    dp.include_router(wallet.router)
    dp.include_router(withdrawal.router)
    dp.include_router(admin.router)
    dp.include_router(help.router)
    dp.include_router(callbacks.router)

    @dp.error()
    async def global_errors(event: ErrorEvent):
        exc = event.exception
        exc_type = type(exc).__name__
        update_type = getattr(getattr(event.update, "event_type", None), "value", "unknown")

        log.error("Handler error. update_type=%s exception_type=%s",
                  update_type, exc_type)
        msg = str(exc)
        if len(msg) > 1000:
            msg = msg[:1000] + "..."
        log.error("Exception message: %s", msg)
        log.debug("Traceback for %s", exc_type, exc_info=(type(exc), exc, exc.__traceback__))

        callback = event.update.callback_query
        if callback is not None:
            try:
                await callback.answer("Произошла ошибка. Попробуйте ещё раз.", show_alert=False)
            except Exception:
                pass

    logger.info("Bot is starting...")

    try:
        await dp.start_polling(bot)
    except TelegramNetworkError as e:
        logger.error(f"Network error: {e}")
        logger.error("Check internet connection and firewall. api.telegram.org:443 must be reachable.")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())