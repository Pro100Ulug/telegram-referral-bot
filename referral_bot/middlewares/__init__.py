from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from referral_bot.database import database as db
from referral_bot.utils.security import is_admin

CALLBACK_LIMIT = 10
CALLBACK_WINDOW_SECONDS = 60
ADMIN_CALLBACK_LIMIT = 30
ADMIN_CALLBACK_WINDOW_SECONDS = 60


class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user and not user.is_bot:
            data["db_user"] = db.get_user(user.id)
        return await handler(event, data)


class CallbackLoggerMiddleware(BaseMiddleware):
    """Rate-limit and audit every callback before it reaches a handler.

    Flow:
        callback received -> identify user -> validate basic shape ->
        rate limit -> if blocked: answer + stop -> handler -> audit log

    The rate-limit is applied BEFORE the handler runs, so heavy/sensitive
    handlers are never reached when the callback should be blocked. The audit
    record is written regardless of what the handler returns.
    """

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if not user or user.is_bot:
            return await handler(event, data)

        action_name = getattr(event, "data", None)
        if not isinstance(action_name, str) or not action_name:
            # No payload -> nothing meaningful to rate-limit/audit; let the
            # handler deal with it (it will likely reject the shape itself).
            return await handler(event, data)

        is_adm = is_admin(user.id)
        action = "callback:admin" if is_adm else "callback"
        limit = ADMIN_CALLBACK_LIMIT if is_adm else CALLBACK_LIMIT
        window = ADMIN_CALLBACK_WINDOW_SECONDS if is_adm else CALLBACK_WINDOW_SECONDS

        safe_detail = action_name[:120]
        if not db.consume_rate_limit(user.id, action, limit, window, details=safe_detail):
            try:
                await event.answer("Слишком много запросов, попробуйте позже", show_alert=True)
            except Exception:
                pass
            return None
        return await handler(event, data)