from aiogram import Router, F
from aiogram.types import Message

from referral_bot.database import database as db
from referral_bot.services import referral_service
from referral_bot.config import calculate_level

router = Router()


@router.message(F.text == "\U0001f464 Профиль")
@router.message(F.text == "/profile")
async def cmd_profile(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся через /start")
        return

    ref_count = referral_service.get_referral_count(user["user_id"])
    confirmed = referral_service.get_confirmed_count(user["user_id"])
    level = calculate_level(user["coins"])

    text = (
        f"Профиль: {user['first_name']}\n\n"
        f"Монеты: {user['coins']}\n"
        f"Уровень: {level}\n"
        f"Приглашено: {ref_count}\n"
        f"Подтверждено: {confirmed}\n"
        f"Регистрация: {user['registered_at'][:10]}"
    )
    await message.answer(text)
