from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from referral_bot.database import database as db
from referral_bot.services import referral_service, wallet_service
from referral_bot.keyboards.menus import main_menu
from referral_bot.utils.security import parse_telegram_id

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.is_bot:
        return
    user_id = message.from_user.id

    if not db.check_rate_limit(user_id, "/start", 5, 60):
        await message.answer("Слишком много запросов, попробуйте позже")
        return

    username = message.from_user.username
    first_name = message.from_user.first_name
    args = message.text.split()

    referred_by = None
    if len(args) > 1:
        ref_id = parse_telegram_id(args[1])
        if ref_id is not None and referral_service.validate_referrer(ref_id, user_id):
            referred_by = ref_id

    is_new = db.add_user(user_id, username, first_name, referred_by)

    if is_new and referred_by:
        referral_service.register_referral(referred_by, user_id)
        referrer = db.get_user(referred_by)
        ref_name = referrer["first_name"] if referrer else "пользователь"
        await message.answer(
            f"Добро пожаловать в партнёрскую программу!\n"
            f"Тебя пригласил {ref_name}.\n\n"
            f"Используй /help чтобы узнать команды.",
            reply_markup=main_menu(),
        )
    elif is_new:
        await message.answer(
            "Добро пожаловать в партнёрскую программу!\n\n"
            "Используй /help чтобы узнать команды.",
            reply_markup=main_menu(),
        )
    else:
        await message.answer("С возвращением!", reply_markup=main_menu())

    db.log_user_action(user_id, "/start")
