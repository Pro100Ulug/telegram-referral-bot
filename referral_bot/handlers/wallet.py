from aiogram import Router, F
from aiogram.types import Message

from referral_bot.database import database as db
from referral_bot.services import wallet_service
from referral_bot.config import (
    calculate_level,
    COLLECT_ATTEMPT_LIMIT,
    COLLECT_ATTEMPT_WINDOW_SECONDS,
)

router = Router()


@router.message(F.text == "\U0001f4b0 Баланс")
@router.message(F.text == "/balance")
async def cmd_balance(message: Message):
    user = wallet_service.get_balance(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся через /start")
        return

    level = calculate_level(user["coins"])
    daily_reward_base = int(db.get_setting("daily_reward_base") or 2)
    daily = level * daily_reward_base

    text = (
        f"Баланс: {user['coins']} монет\n"
        f"Уровень: {level}\n"
        f"Ежедневная награда: {daily}\n\n"
        f"Нажми 'Собрать награду' или используй /collect"
    )
    await message.answer(text)


@router.message(F.text == "\U0001f381 Ежедневная награда")
@router.message(F.text == "/collect")
async def cmd_collect(message: Message):
    user_id = message.from_user.id

    if not db.consume_rate_limit(
        user_id, "collect_attempt", COLLECT_ATTEMPT_LIMIT, COLLECT_ATTEMPT_WINDOW_SECONDS
    ):
        await message.answer("Слишком много запросов, попробуйте позже")
        return

    result, status = wallet_service.collect_daily(user_id)

    if status == "user_not_found":
        await message.answer("Сначала зарегистрируйся через /start")
        return

    if status == "too_early":
        await message.answer("Можно собрать только раз в 24 часа.")
        return

    await message.answer(
        f"Ты собрал {result['reward']} монет!\n"
        f"Баланс: {result['coins']}\n"
        f"Уровень: {result['level']}"
    )

    db.log_user_action(user_id, "/collect")


@router.message(F.text == "/top")
async def cmd_top(message: Message):
    users = wallet_service.get_top_users(10)
    if not users:
        await message.answer("Пока нет пользователей.")
        return

    medals = ["1.", "2.", "3."]
    lines = ["Топ-10:\n"]
    for i, u in enumerate(users):
        prefix = medals[i] if i < 3 else f"  {i+1}."
        name = u["first_name"] or u["username"] or str(u["user_id"])
        lines.append(f"{prefix} {name} — {u['coins']} монет")

    await message.answer("\n".join(lines))


@router.message(F.text == "/history")
async def cmd_history(message: Message):
    user = wallet_service.get_balance(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся через /start")
        return

    txs, total_pages = db.get_user_transactions_page(user["user_id"], 1)
    if not txs:
        await message.answer("У тебя пока нет транзакций.")
        return

    lines = [f"\U0001f4b3 \u0418\u0441\u0442\u043e\u0440\u0438\u044f (\u0441\u0442\u0440. 1/{total_pages}):\n"]
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        date = tx["created_at"][:10]
        lines.append(f"  {date} {sign}{tx['amount']} \u2014 {tx['reason']}")

    from referral_bot.keyboards.admin_panel import user_history_page_keyboard_user
    kb = user_history_page_keyboard_user(user["user_id"], 1, total_pages)
    await message.answer("\n".join(lines), reply_markup=kb)
