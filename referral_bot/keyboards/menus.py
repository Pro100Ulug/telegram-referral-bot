from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001f464 Профиль"), KeyboardButton(text="\U0001f4b0 Баланс")],
            [KeyboardButton(text="\U0001f465 Рефералы"), KeyboardButton(text="\U0001f381 Ежедневная награда")],
            [KeyboardButton(text="\U0001f4b8 Вывод")],
        ],
        resize_keyboard=True,
    )
