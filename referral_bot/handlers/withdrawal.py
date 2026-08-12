from aiogram import Router, F
from aiogram.types import Message

from referral_bot.database import database as db
from referral_bot.services import withdrawal_service
from referral_bot.config import MIN_WITHDRAW_AMOUNT as DEFAULT_MIN_WITHDRAW
from referral_bot.utils.security import parse_positive_int

router = Router()


@router.message(F.text == "\U0001f4b8 \u0412\u044b\u0432\u043e\u0434")
@router.message(F.text == "/withdraw")
async def cmd_withdraw_info(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u0443\u0439\u0441\u044f \u0447\u0435\u0440\u0435\u0437 /start")
        return

    min_withdraw = int(db.get_setting("min_withdraw_amount") or DEFAULT_MIN_WITHDRAW)
    withdrawals, total_pages = db.get_user_withdrawals_page(message.from_user.id, 1)
    lines = [
        f"\U0001f4b0 \u0411\u0430\u043b\u0430\u043d\u0441: {user['coins']} \u043c\u043e\u043d\u0435\u0442\n",
        f"\U0001f4b8 \u041c\u0438\u043d\u0438\u043c\u0443\u043c \u0434\u043b\u044f \u0432\u044b\u0432\u043e\u0434\u0430: {min_withdraw}\n",
        "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435: /withdraw \u0421\u0423\u041c\u041c\u0410 \u0420\u0415\u041a\u0412\u0418\u0437\u0418\u0422\u042b\n",
        "\u041f\u0440\u0438\u043c\u0435\u0440: /withdraw 100 \u041a\u0430\u0440\u0442\u0430 1234 5678 9012 3456\n",
    ]

    if withdrawals:
        lines.append(f"\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 \u0437\u0430\u044f\u0432\u043a\u0438 (\u0441\u0442\u0440. 1/{total_pages}):\n")
        statuses = {"pending": "\u043e\u0436\u0438\u0434\u0430\u0435\u0442", "approved": "\u043e\u0434\u043e\u0431\u0440\u0435\u043d\u0430", "rejected": "\u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0430"}
        for w in withdrawals:
            status = statuses.get(w["status"], w["status"])
            date = w["created_at"][:10]
            lines.append(f"  {date} \u2014 {w['amount']} \u2014 {status}")

    from referral_bot.keyboards.admin_panel import user_withdrawals_page_keyboard
    kb = user_withdrawals_page_keyboard(1, total_pages)
    await message.answer("\n".join(lines), reply_markup=kb)


@router.message(F.text.startswith("/withdraw "))
async def cmd_withdraw_create(message: Message):
    parts = message.text.split(maxsplit=2)
    user_id = message.from_user.id

    if not db.check_rate_limit(user_id, "/withdraw", 3, 60):
        await message.answer("Слишком много запросов, попробуйте позже")
        return

    if len(parts) < 3:
        await message.answer("\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435: /withdraw \u0421\u0423\u041c\u041c\u0410 \u0420\u0415\u041a\u0412\u0418\u0437\u0418\u0422\u042b")
        return

    if db.has_pending_withdrawal(user_id):
        await message.answer("\u0423 \u0442\u0435\u0431\u044f \u0443\u0436\u0435 \u0435\u0441\u0442\u044c \u043e\u0436\u0438\u0434\u0430\u044e\u0449\u0430\u044f \u0437\u0430\u044f\u0432\u043a\u0430. \u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u0435\u0451 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438.")
        return

    amount = parse_positive_int(parts[1])
    if amount is None:
        await message.answer("Сумма должна быть положительным числом.")
        return

    details = parts[2]

    result, status = withdrawal_service.create_withdrawal(user_id, amount, details)

    if status == "user_not_found":
        await message.answer("\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u0443\u0439\u0441\u044f \u0447\u0435\u0440\u0435\u0437 /start")
    elif status == "already_pending":
        await message.answer("\u0423 \u0442\u0435\u0431\u044f \u0443\u0436\u0435 \u0435\u0441\u0442\u044c \u043e\u0436\u0438\u0434\u0430\u044e\u0449\u0430\u044f \u0437\u0430\u044f\u0432\u043a\u0430. \u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u0435\u0451 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438.")
    elif status == "invalid_amount":
        await message.answer("\u0421\u0443\u043c\u043c\u0430 \u0434\u043e\u043b\u0436\u043d\u0430 \u0431\u044b\u0442\u044c \u0431\u043e\u043b\u044c\u0448\u0435 \u043d\u0443\u043b\u044f.")
    elif status == "insufficient_balance":
        await message.answer("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u043c\u043e\u043d\u0435\u0442 \u043d\u0430 \u0431\u0430\u043b\u0430\u043d\u0441\u0435.")
    elif status == "min_amount":
        min_withdraw = int(db.get_setting("min_withdraw_amount") or DEFAULT_MIN_WITHDRAW)
        await message.answer(f"\u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u0430\u044f \u0441\u0443\u043c\u043c\u0430 \u0432\u044b\u0432\u043e\u0434\u0430: {min_withdraw}")
    else:
        await message.answer(
            f"\u0417\u0430\u044f\u0432\u043a\u0430 \u0441\u043e\u0437\u0434\u0430\u043d\u0430!\n"
            f"\u0421\u0443\u043c\u043c\u0430: {amount}\n"
            f"\u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b: {details}\n"
            f"\u0411\u0430\u043b\u0430\u043d\u0441: {result['coins']}\n\n"
            f"\u041e\u0436\u0438\u0434\u0430\u0439\u0442\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u043c."
        )
        db.log_user_action(user_id, "/withdraw", f"amount={amount}")


@router.message(F.text == "/my_withdrawals")
async def cmd_my_withdrawals(message: Message):
    user_id = message.from_user.id
    withdrawals, total_pages = db.get_user_withdrawals_page(user_id, 1)

    if not withdrawals:
        await message.answer("\u0423 \u0442\u0435\u0431\u044f \u043d\u0435\u0442 \u0437\u0430\u044f\u0432\u043e\u043a \u043d\u0430 \u0432\u044b\u0432\u043e\u0434.")
        return

    statuses = {"pending": "\u043e\u0436\u0438\u0434\u0430\u0435\u0442", "approved": "\u043e\u0434\u043e\u0431\u0440\u0435\u043d\u0430", "rejected": "\u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0430"}
    lines = [f"\U0001f4b8 \u0422\u0432\u043e\u0438 \u0437\u0430\u044f\u0432\u043a\u0438 (\u0441\u0442\u0440. 1/{total_pages}):\n"]
    for w in withdrawals:
        status = statuses.get(w["status"], w["status"])
        date = w["created_at"][:10]
        comment = f" ({w['admin_comment']})" if w["admin_comment"] else ""
        lines.append(f"  #{w['id']} {date} \u2014 {w['amount']} \u2014 {status}{comment}")

    from referral_bot.keyboards.admin_panel import user_withdrawals_page_keyboard
    kb = user_withdrawals_page_keyboard(1, total_pages)
    await message.answer("\n".join(lines), reply_markup=kb)
