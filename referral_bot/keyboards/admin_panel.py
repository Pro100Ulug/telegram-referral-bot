from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\U0001f465 Пользователи", callback_data="adm:users:1"),
                InlineKeyboardButton(text="\U0001f4b0 Баланс", callback_data="adm:balance"),
            ],
            [
                InlineKeyboardButton(text="\U0001f4ca Статистика", callback_data="adm:stats"),
                InlineKeyboardButton(text="\U0001f4b8 Выводы", callback_data="adm:wd:1"),
            ],
            [
                InlineKeyboardButton(text="\U0001f3c6 Топ", callback_data="adm:top"),
                InlineKeyboardButton(text="\u2699\ufe0f Настройки", callback_data="adm:settings"),
            ],
        ]
    )


def pagination_keyboard(prefix: str, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    if total_pages <= 1:
        return InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    nav = []
    if current_page > 1:
        nav.append(InlineKeyboardButton(text="\U0001f519", callback_data=f"{prefix}:{current_page - 1}"))
    nav.append(InlineKeyboardButton(text=f"\U0001f4c4 {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav.append(InlineKeyboardButton(text="\U0001f51a", callback_data=f"{prefix}:{current_page + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="adm:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_detail_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\U0001f4b0 \u0422\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438", callback_data=f"adm:utx:{user_id}:1"),
            ],
            [
                InlineKeyboardButton(text="\U0001f519 \u041d\u0430\u0437\u0430\u0434", callback_data="adm:users:1"),
            ],
        ]
    )


def withdrawal_detail_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\u2705 \u041e\u0434\u043e\u0431\u0440\u0438\u0442\u044c", callback_data=f"adm:wd_ap:{withdrawal_id}"),
                InlineKeyboardButton(text="\u274c \u041e\u0442\u043a\u043b\u043e\u043d\u0438\u0442\u044c", callback_data=f"adm:wd_rj:{withdrawal_id}"),
            ],
            [
                InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="adm:wd:1"),
            ],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\u270f\ufe0f \u0411\u043e\u043d\u0443\u0441 \u0437\u0430 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435", callback_data="adm:set:referral_bonus"),
            ],
            [
                InlineKeyboardButton(text="\u270f\ufe0f \u041c\u0438\u043d. \u0432\u044b\u0432\u043e\u0434", callback_data="adm:set:min_withdraw_amount"),
                InlineKeyboardButton(text="\u270f\ufe0f \u0415\u0436\u0435\u0434\u043d. \u043d\u0430\u0433\u0440\u0430\u0434\u0430", callback_data="adm:set:daily_reward_base"),
            ],
            [
                InlineKeyboardButton(text="\u270f\ufe0f \u0423\u0441\u043b\u043e\u0432\u0438\u0435 \u0431\u043e\u043d\u0443\u0441\u0430", callback_data="adm:set:referral_bonus_condition"),
            ],
            [
                InlineKeyboardButton(text="\U0001f504 \u0421\u0431\u0440\u043e\u0441\u0438\u0442\u044c \u043a \u0434\u0435\u0444\u043e\u043b\u0442\u0430\u043c", callback_data="adm:settings_reset"),
            ],
            [
                InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="adm:main"),
            ],
        ]
    )


def user_history_page_keyboard(user_id: int, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    if total_pages <= 1:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data=f"adm:user:{user_id}")]
            ]
        )
    buttons = []
    nav = []
    if current_page > 1:
        nav.append(InlineKeyboardButton(text="\U0001f519", callback_data=f"adm:utx:{user_id}:{current_page - 1}"))
    nav.append(InlineKeyboardButton(text=f"\U0001f4c4 {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav.append(InlineKeyboardButton(text="\U0001f51a", callback_data=f"adm:utx:{user_id}:{current_page + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data=f"adm:user:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_history_page_keyboard_user(user_id: int, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    if total_pages <= 1:
        return InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    nav = []
    if current_page > 1:
        nav.append(InlineKeyboardButton(text="\U0001f519", callback_data=f"uhist:{current_page - 1}"))
    nav.append(InlineKeyboardButton(text=f"\U0001f4c4 {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav.append(InlineKeyboardButton(text="\U0001f51a", callback_data=f"uhist:{current_page + 1}"))
    buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_partners_page_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    if total_pages <= 1:
        return InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    nav = []
    if current_page > 1:
        nav.append(InlineKeyboardButton(text="\U0001f519", callback_data=f"upart:{current_page - 1}"))
    nav.append(InlineKeyboardButton(text=f"\U0001f4c4 {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav.append(InlineKeyboardButton(text="\U0001f51a", callback_data=f"upart:{current_page + 1}"))
    buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_withdrawals_page_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    if total_pages <= 1:
        return InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    nav = []
    if current_page > 1:
        nav.append(InlineKeyboardButton(text="\U0001f519", callback_data=f"uwd:{current_page - 1}"))
    nav.append(InlineKeyboardButton(text=f"\U0001f4c4 {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav.append(InlineKeyboardButton(text="\U0001f51a", callback_data=f"uwd:{current_page + 1}"))
    buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)
