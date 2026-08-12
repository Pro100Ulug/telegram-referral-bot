from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from referral_bot.database import database as db
from referral_bot.services import referral_service

router = Router()


@router.message(F.text == "\U0001f465 \u0420\u0435\u0444\u0435\u0440\u0430\u043b\u044b")
@router.message(F.text == "/referral")
async def cmd_referral(message: Message):
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_id}"

    total = referral_service.get_referral_count(user_id)
    confirmed = referral_service.get_confirmed_count(user_id)

    text = (
        f"\u0422\u0432\u043e\u044f \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u0441\u043a\u0430\u044f \u0441\u0441\u044b\u043b\u043a\u0430:\n{link}\n\n"
        f"\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u043e: {total}\n"
        f"\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e: {confirmed}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\u041f\u043e\u0434\u0435\u043b\u0438\u0442\u044c\u0441\u044f \u0441\u0441\u044b\u043b\u043a\u043e\u0439", switch_inline_query="")]
        ]
    )
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text == "/partners")
async def cmd_partners(message: Message):
    user_id = message.from_user.id
    refs, total_pages = db.get_user_referrals_page(user_id, 1)

    if not refs:
        await message.answer(
            "\u0423 \u0442\u0435\u0431\u044f \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0451\u043d\u043d\u044b\u0445.\n"
            "\u041f\u043e\u0434\u0435\u043b\u0438\u0441\u044c \u0441\u0441\u044b\u043b\u043a\u043e\u0439: /referral"
        )
        return

    lines = [f"\U0001f465 \u0422\u0432\u043e\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0451\u043d\u043d\u044b\u0435 (\u0441\u0442\u0440. 1/{total_pages}):\n"]
    for ref in refs:
        name = ref["first_name"] or ref["username"] or str(ref["user_id"])
        status = "\u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d" if ref["reward_status"] == "confirmed" else "\u043e\u0436\u0438\u0434\u0430\u0435\u0442"
        lines.append(f"  {name} \u2014 {status}")

    from referral_bot.keyboards.admin_panel import user_partners_page_keyboard
    kb = user_partners_page_keyboard(1, total_pages)
    await message.answer("\n".join(lines), reply_markup=kb)
