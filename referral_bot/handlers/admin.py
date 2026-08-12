from aiogram import Router, F
from aiogram.types import Message

from referral_bot.database import database as db
from referral_bot.services import referral_service, withdrawal_service
from referral_bot.keyboards.admin_panel import admin_main_menu, settings_keyboard
from referral_bot.utils.security import is_admin, parse_positive_int, parse_telegram_id

router = Router()


@router.message(F.text == "/admin")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.")
        return
    await message.answer("\U0001f3e0 \u041f\u0430\u043d\u0435\u043b\u044c \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f", reply_markup=admin_main_menu())


@router.message(F.text == "/settings")
async def cmd_settings(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.")
        return
    settings = db.get_all_settings()
    condition_labels = {
        "none": "нет", "hours_24": "24ч", "active": "актив", "daily_collect": "награда",
    }
    cond_label = condition_labels.get(settings['referral_bonus_condition'], settings['referral_bonus_condition'])
    text = (
        f"\u2699\ufe0f \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u043f\u0440\u043e\u0435\u043a\u0442\u0430\n\n"
        f"\U0001f381 \u0411\u043e\u043d\u0443\u0441 \u0437\u0430 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435: {settings['referral_bonus']}\n"
        f"\U0001f4b0 \u041c\u0438\u043d. \u0432\u044b\u0432\u043e\u0434: {settings['min_withdraw_amount']} \u043c\u043e\u043d\u0435\u0442\n"
        f"\U0001f381 \u0415\u0436\u0435\u0434\u043d. \u043d\u0430\u0433\u0440\u0430\u0434\u0430: {settings['daily_reward_base']} \u043c\u043e\u043d\u0435\u0442\n"
        f"\U0001f512 \u0423\u0441\u043b\u043e\u0432\u0438\u0435 \u0431\u043e\u043d\u0443\u0441\u0430: {cond_label}"
    )
    await message.answer(text, reply_markup=settings_keyboard())


@router.message(F.text.startswith("/confirm "))
async def cmd_confirm(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /confirm USER_ID")
        return

    target_id = parse_telegram_id(parts[1])
    if target_id is None:
        await message.answer("USER_ID должен быть положительным числом.")
        return

    target = db.get_user(target_id)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    if not target["referred_by"]:
        await message.answer(f"У пользователя {target_id} нет реферера.")
        return

    if not db.is_reward_pending(target_id):
        await message.answer(f"Бонус за {target_id} уже начислен или не ожидается.")
        return

    if not db.check_referral_bonus_condition(target_id):
        condition = db.get_setting("referral_bonus_condition")
        await message.answer(f"Бонус за {target_id} недоступен (условие: {condition}).")
        return

    reward = referral_service.confirm_reward(target_id, message.from_user.id)
    if reward:
        referrer = db.get_user(reward["referrer_id"])
        ref_name = referrer["first_name"] if referrer else str(reward["referrer_id"])
        await message.answer(
            f"Бонус начислен!\n"
            f"Пригласивший: {ref_name} (ID: {reward['referrer_id']})\n"
            f"Сумма: +{reward['amount']} монет"
        )
    else:
        await message.answer("Ошибка при начислении.")


@router.message(F.text == "/pending")
async def cmd_pending(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    rewards_list = referral_service.get_pending_rewards()
    if not rewards_list:
        await message.answer("Нет ожидающих подтверждения.")
        return

    lines = ["Ожидающие:\n"]
    for r in rewards_list:
        name = r["first_name"] or r["username"] or str(r["referred_user_id"])
        lines.append(
            f"  ID: {r['referred_user_id']} | {name} | "
            f"Реферал: {r['referrer_id']} | Бонус: {r['amount']}"
        )
    lines.append("\nИспользуй /confirm USER_ID")
    await message.answer("\n".join(lines))


@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    total = db.get_total_users()
    pending_list = referral_service.get_pending_rewards()

    await message.answer(
        f"Статистика:\n"
        f"Пользователей: {total}\n"
        f"Ожидающих: {len(pending_list)}"
    )


@router.message(F.text == "/withdrawals")
async def cmd_withdrawals(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    withdrawals = withdrawal_service.get_pending_withdrawals()
    if not withdrawals:
        await message.answer("Нет ожидающих заявок.")
        return

    lines = ["Ожидающие заявки:\n"]
    for w in withdrawals:
        name = w["first_name"] or w["username"] or str(w["user_id"])
        date = w["created_at"][:10]
        lines.append(
            f"#{w['id']} | {name} (ID: {w['user_id']}) | "
            f"{w['amount']} | {w['details']} | {date}"
        )
    lines.append("\n/approve ID или /reject ID КОММЕНТАРИЙ")
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("/approve "))
async def cmd_approve(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /approve WITHDRAWAL_ID")
        return

    withdrawal_id = parse_positive_int(parts[1])
    if withdrawal_id is None:
        await message.answer("ID должен быть положительным числом.")
        return

    result = withdrawal_service.approve_withdrawal(withdrawal_id, message.from_user.id)
    if not result:
        await message.answer(f"Заявка #{withdrawal_id} не найдена или уже обработана.")
        return

    await message.answer(
        f"Заявка #{withdrawal_id} одобрена!\n"
        f"Пользователь: {result['user_id']}\n"
        f"Сумма: {result['amount']}"
    )

    try:
        await message.bot.send_message(
            result["user_id"],
            f"✅ Ваш вывод на сумму {result['amount']} монет одобрен."
        )
    except Exception:
        pass


@router.message(F.text.startswith("/addcoins "))
async def cmd_addcoins(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    from referral_bot.config import MAX_ADMIN_ADD_COINS

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /addcoins USER_ID AMOUNT")
        return

    target_id = parse_telegram_id(parts[1])
    amount = parse_positive_int(parts[2], max_value=MAX_ADMIN_ADD_COINS)
    if target_id is None or amount is None:
        await message.answer("USER_ID и AMOUNT должны быть положительными числами.")
        return

    target = db.get_user(target_id)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    ok = db.add_balance_transaction(target_id, amount, "credit", "admin_add")
    if not ok:
        await message.answer("Ошибка при начислении.")
        return

    db.log_user_action(
        message.from_user.id,
        "admin_add_coins",
        f"admin={message.from_user.id} user={target_id} amount={amount}"
    )

    user = db.get_user(target_id)
    await message.answer(
        f"Начислено {amount} монет пользователю {target_id}\n"
        f"Баланс: {user['coins']} монет"
    )

    try:
        await message.bot.send_message(
            target_id,
            f"Администратор начислил вам +{amount} монет.\n"
            f"Баланс: {user['coins']} монет"
        )
    except Exception:
        pass


@router.message(F.text.startswith("/reject "))
async def cmd_reject(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только для администраторов.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: /reject WITHDRAWAL_ID КОММЕНТАРИЙ")
        return

    withdrawal_id = parse_positive_int(parts[1])
    if withdrawal_id is None:
        await message.answer("ID должен быть положительным числом.")
        return

    comment = parts[2] if len(parts) > 2 else ""

    result = withdrawal_service.reject_withdrawal(withdrawal_id, message.from_user.id, comment)
    if not result:
        await message.answer(f"Заявка #{withdrawal_id} не найдена или уже обработана.")
        return

    await message.answer(
        f"Заявка #{withdrawal_id} отклонена.\n"
        f"Пользователь: {result['user_id']}\n"
        f"Сумма: {result['amount']} (возвращена)\n"
        f"Комментарий: {comment or 'нет'}"
    )
