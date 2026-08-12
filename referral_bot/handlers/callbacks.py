from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from referral_bot.database import database as db
from referral_bot.services import withdrawal_service, referral_service
from referral_bot.keyboards.admin_panel import (
    admin_main_menu,
    pagination_keyboard,
    user_detail_keyboard,
    withdrawal_detail_keyboard,
    settings_keyboard,
    user_history_page_keyboard,
    user_history_page_keyboard_user,
    user_partners_page_keyboard,
    user_withdrawals_page_keyboard,
)
from referral_bot.utils.security import is_admin, parse_positive_int, parse_non_negative_int, parse_telegram_id

router = Router()


class AdminFSM(StatesGroup):
    reject_withdrawal = State()
    edit_setting = State()


def _format_user(u):
    name = u.get("first_name") or u.get("username") or str(u["user_id"])
    return f"{name} (ID: {u['user_id']}) \u2014 {u['coins']} \u043c\u043e\u043d\u0435\u0442"


@router.callback_query(F.data == "adm:main")
async def cb_admin_main(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    await callback.message.edit_text("\U0001f3e0 \u041f\u0430\u043d\u0435\u043b\u044c \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f", reply_markup=admin_main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("adm:users:"))
async def cb_admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    page = parse_positive_int(parts[2]) if len(parts) > 2 else None
    if page is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    users, total_pages = db.get_users_page(page)
    if not users:
        await callback.message.edit_text("\u041d\u0435\u0442 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439.", reply_markup=admin_main_menu())
        await callback.answer()
        return
    lines = [f"\U0001f465 \u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438 (\u0441\u0442\u0440. {page}/{total_pages}):\n"]
    for u in users:
        lines.append(f"  {_format_user(u)}")
    kb = pagination_keyboard("adm:users", page, total_pages)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:user:"))
async def cb_admin_user_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    user_id = parse_telegram_id(parts[2]) if len(parts) > 2 else None
    if user_id is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    user = db.get_user(user_id)
    if not user:
        await callback.answer("\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", show_alert=True)
        return
    ref_count = referral_service.get_referral_count(user_id)
    confirmed = referral_service.get_confirmed_count(user_id)
    text = (
        f"\U0001f464 \u041f\u0440\u043e\u0444\u0438\u043b\u044c\n\n"
        f"\u0418\u043c\u044f: {user['first_name']}\n"
        f"ID: {user['user_id']}\n"
        f"\U0001f4b0 \u0411\u0430\u043b\u0430\u043d\u0441: {user['coins']} \u043c\u043e\u043d\u0435\u0442\n"
        f"\U0001f3af \u0423\u0440\u043e\u0432\u0435\u043d\u044c: {user['level']}\n"
        f"\U0001f465 \u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u043e: {ref_count}\n"
        f"\u2705 \u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e: {confirmed}\n"
        f"\U0001f4c5 \u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f: {user['registered_at'][:10]}"
    )
    await callback.message.edit_text(text, reply_markup=user_detail_keyboard(user_id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:utx:"))
async def cb_admin_user_transactions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    user_id = parse_telegram_id(parts[2])
    page = parse_positive_int(parts[3])
    if user_id is None or page is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    txs, total_pages = db.get_user_transactions_page(user_id, page)
    if not txs:
        await callback.message.edit_text("\u041d\u0435\u0442 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0439.", reply_markup=user_detail_keyboard(user_id))
        await callback.answer()
        return
    lines = [f"\U0001f4b3 \u0422\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 (\u0441\u0442\u0440. {page}/{total_pages}):\n"]
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        date = tx["created_at"][:10]
        lines.append(f"  {date} {sign}{tx['amount']} \u2014 {tx['reason']}")
    kb = user_history_page_keyboard(user_id, page, total_pages)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm:balance")
async def cb_admin_balance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    total_coins = db.get_total_coins()
    stats = db.get_withdrawals_stats()
    pending_wd = stats.get("pending", {"count": 0, "sum": 0})
    approved_wd = stats.get("approved", {"count": 0, "sum": 0})
    text = (
        f"\U0001f4b0 \u0411\u0430\u043b\u0430\u043d\u0441 \u0441\u0438\u0441\u0442\u0435\u043c\u044b\n\n"
        f"\U0001f4b3 \u0412\u0441\u0435\u0433\u043e \u043c\u043e\u043d\u0435\u0442 \u0432 \u043e\u0431\u043e\u0440\u043e\u0442\u0435: {total_coins}\n\n"
        f"\U0001f4b8 \u0412\u044b\u0432\u043e\u0434\u044b:\n"
        f"  \u041e\u0436\u0438\u0434\u0430\u044e\u0442: {pending_wd['count']} ({pending_wd['sum']} \u043c\u043e\u043d\u0435\u0442)\n"
        f"  \u041e\u0434\u043e\u0431\u0440\u0435\u043d\u043e: {approved_wd['count']} ({approved_wd['sum']} \u043c\u043e\u043d\u0435\u0442)"
    )
    await callback.message.edit_text(text, reply_markup=admin_main_menu())
    await callback.answer()


@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    total = db.get_total_users()
    today = db.get_users_count_since(1)
    week = db.get_users_count_since(7)
    active = db.get_active_users_count()
    pending = len(referral_service.get_pending_rewards())
    text = (
        f"\U0001f4ca \u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430\n\n"
        f"\U0001f465 \u0412\u0441\u0435\u0433\u043e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439: {total}\n"
        f"\U0001f4c5 \u0417\u0430 \u0441\u0435\u0433\u043e\u0434\u043d\u044f: {today}\n"
        f"\U0001f4c5 \u0417\u0430 \u043d\u0435\u0434\u0435\u043b\u044e: {week}\n"
        f"\u23f0 \u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445 (24\u0447): {active}\n"
        f"\u23f3 \u041e\u0436\u0438\u0434\u0430\u044e\u0449\u0438\u0445 \u0431\u043e\u043d\u0443\u0441\u043e\u0432: {pending}"
    )
    await callback.message.edit_text(text, reply_markup=admin_main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("adm:wd:"))
async def cb_admin_withdrawals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    page = parse_positive_int(parts[2]) if len(parts) > 2 else None
    if page is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    withdrawals, total_pages = db.get_pending_withdrawals_page(page)
    if not withdrawals:
        await callback.message.edit_text("\u041d\u0435\u0442 \u043e\u0436\u0438\u0434\u0430\u044e\u0449\u0438\u0445 \u0437\u0430\u044f\u0432\u043e\u043a.", reply_markup=admin_main_menu())
        await callback.answer()
        return
    lines = [f"\U0001f4b8 \u0417\u0430\u044f\u0432\u043a\u0438 \u043d\u0430 \u0432\u044b\u0432\u043e\u0434 (\u0441\u0442\u0440. {page}/{total_pages}):\n"]
    for w in withdrawals:
        name = w["first_name"] or w["username"] or str(w["user_id"])
        date = w["created_at"][:10]
        lines.append(f"  #{w['id']} | {name} | {w['amount']} \u043c\u043e\u043d\u0435\u0442 | {date}")
    kb = pagination_keyboard("adm:wd", page, total_pages)
    for w in withdrawals:
        kb.inline_keyboard.insert(0, [
            InlineKeyboardButton(text=f"#{w['id']} \u041f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435", callback_data=f"adm:wd_d:{w['id']}"),
        ])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:wd_d:"))
async def cb_admin_withdrawal_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    wd_id = parse_positive_int(parts[2]) if len(parts) > 2 else None
    if wd_id is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT w.*, u.first_name, u.username "
            "FROM withdrawals w JOIN users u ON w.user_id = u.user_id "
            "WHERE w.id = ?", (wd_id,)
        )
        row = cursor.fetchone()
    finally:
        conn.close()
    if not row:
        await callback.answer("\u0417\u0430\u044f\u0432\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430.", show_alert=True)
        return
    w = dict(row)
    name = w["first_name"] or w["username"] or str(w["user_id"])
    date = w["created_at"][:10]
    statuses = {"pending": "\u043e\u0436\u0438\u0434\u0430\u0435\u0442", "approved": "\u043e\u0434\u043e\u0431\u0440\u0435\u043d\u0430", "rejected": "\u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0430"}
    text = (
        f"\U0001f4b8 \u0417\u0430\u044f\u0432\u043a\u0432\u0430 #{w['id']}\n\n"
        f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c: {name} (ID: {w['user_id']})\n"
        f"\u0421\u0443\u043c\u043c\u0430: {w['amount']} \u043c\u043e\u043d\u0435\u0442\n"
        f"\u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b: {w['details']}\n"
        f"\u0421\u0442\u0430\u0442\u0443\u0441: {statuses.get(w['status'], w['status'])}\n"
        f"\u0414\u0430\u0442\u0430: {date}"
    )
    if w["admin_comment"]:
        text += f"\n\u041a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0439: {w['admin_comment']}"
    await callback.message.edit_text(text, reply_markup=withdrawal_detail_keyboard(wd_id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:wd_ap:"))
async def cb_admin_withdrawal_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    wd_id = parse_positive_int(parts[2]) if len(parts) > 2 else None
    if wd_id is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    result = withdrawal_service.approve_withdrawal(wd_id, callback.from_user.id)
    if not result:
        await callback.answer("\u0417\u0430\u044f\u0432\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430 \u0438\u043b\u0438 \u0443\u0436\u0435 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u0430.", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        f"\u2705 \u0417\u0430\u044f\u0432\u043a\u0430 #{wd_id} \u043e\u0434\u043e\u0431\u0440\u0435\u043d\u0430!\n"
        f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c: {result['user_id']}\n"
        f"\u0421\u0443\u043c\u043c\u0430: {result['amount']}"
    )
    try:
        await callback.bot.send_message(
            result["user_id"],
            f"\u2705 \u0412\u0430\u0448 \u0432\u044b\u0432\u043e\u0434 \u043d\u0430 \u0441\u0443\u043c\u043c\u0443 {result['amount']} \u043c\u043e\u043d\u0435\u0442 \u043e\u0434\u043e\u0431\u0440\u0435\u043d."
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("adm:wd_rj:"))
async def cb_admin_withdrawal_reject_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    parts = callback.data.split(":")
    wd_id = parse_positive_int(parts[2]) if len(parts) > 2 else None
    if wd_id is None:
        await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
        return
    await state.update_data(withdrawal_id=wd_id)
    await state.set_state(AdminFSM.reject_withdrawal)
    await callback.message.edit_text(
        f"\u274c \u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u0440\u0438\u0447\u0438\u043d\u0443 \u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0438\u044f \u0437\u0430\u044f\u0432\u043a\u0438 #{wd_id}:"
    )
    await callback.answer()


@router.message(StateFilter(AdminFSM.reject_withdrawal))
async def cb_admin_withdrawal_reject_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    wd_id = data.get("withdrawal_id")
    comment = message.text
    result = withdrawal_service.reject_withdrawal(wd_id, message.from_user.id, comment)
    await state.clear()
    if not result:
        await message.answer("\u0417\u0430\u044f\u0432\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430 \u0438\u043b\u0438 \u0443\u0436\u0435 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u0430.")
        return
    await message.answer(
        f"\u274c \u0417\u0430\u044f\u0432\u043a\u0430 #{wd_id} \u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0430.\n"
        f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c: {result['user_id']}\n"
        f"\u0421\u0443\u043c\u043c\u0430: {result['amount']} (\u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0435\u043d\u0430)\n"
        f"\u041f\u0440\u0438\u0447\u0438\u043d\u0430: {comment}"
    )
    try:
        user = db.get_user(result["user_id"])
        if user:
            await message.bot.send_message(
                result["user_id"],
                f"\u274c \u0412\u0430\u0448\u0430 \u0437\u0430\u044f\u0432\u043a\u0430 \u043d\u0430 \u0432\u044b\u0432\u043e\u0434 \u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0430.\n\n\u041f\u0440\u0438\u0447\u0438\u043d\u0430:\n{comment}"
            )
    except Exception:
        pass


@router.callback_query(F.data == "adm:top")
async def cb_admin_top(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    users = db.get_top_users(10)
    if not users:
        await callback.message.edit_text("\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439.", reply_markup=admin_main_menu())
        await callback.answer()
        return
    medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
    lines = ["\U0001f3c6 \u0422\u043e\u043f-10:\n"]
    for i, u in enumerate(users):
        prefix = medals[i] if i < 3 else f"  {i+1}."
        name = u["first_name"] or u["username"] or str(u["user_id"])
        lines.append(f"{prefix} {name} \u2014 {u['coins']} \u043c\u043e\u043d\u0435\u0442")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_main_menu())
    await callback.answer()


@router.callback_query(F.data == "adm:settings")
async def cb_admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только для администраторов.", show_alert=True)
        return
    settings = db.get_all_settings()
    condition_labels = {
        "none": "нет", "hours_24": "24ч", "active": "актив", "daily_collect": "награда",
    }
    cond_label = condition_labels.get(settings['referral_bonus_condition'], settings['referral_bonus_condition'])
    text = (
        f"\u2699\ufe0f Настройки проекта\n\n"
        f"\U0001f381 Бонус за приглашение: {settings['referral_bonus']}\n"
        f"\U0001f4b0 Мин. вывод: {settings['min_withdraw_amount']} монет\n"
        f"\U0001f381 Ежедн. награда: {settings['daily_reward_base']} монет\n"
        f"\U0001f512 Условие бонуса: {cond_label}"
    )
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("adm:set:"))
async def cb_admin_set_setting(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только для администраторов.", show_alert=True)
        return
    key = callback.data.split(":")[2]
    names = {
        "referral_bonus": "Бонус за приглашение",
        "min_withdraw_amount": "Мин. сумма вывода",
        "daily_reward_base": "Ежедн. награда",
        "referral_bonus_condition": "Условие бонуса",
    }
    if key not in names:
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    name = names.get(key, key)
    current = db.get_setting(key)
    await state.update_data(setting_key=key)
    await state.set_state(AdminFSM.edit_setting)

    if key == "referral_bonus_condition":
        from referral_bot.database import REFERRAL_BONUS_CONDITIONS
        options = ", ".join(REFERRAL_BONUS_CONDITIONS)
        await callback.message.edit_text(
            f"\u270f\ufe0f Изменить: {name}\n\n"
            f"Текущее значение: {current}\n\n"
            f"Варианты: {options}\n\n"
            f"Введите новое значение:"
        )
    else:
        await callback.message.edit_text(
            f"\u270f\ufe0f Изменить: {name}\n\n"
            f"Текущее значение: {current}\n\n"
            f"Введите новое число:"
        )
    await callback.answer()


@router.message(StateFilter(AdminFSM.edit_setting))
async def cb_admin_set_setting_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("Отправьте текстовое значение.")
        return
    data = await state.get_data()
    key = data.get("setting_key")
    value = message.text.strip()

    if key == "referral_bonus_condition":
        from referral_bot.database import REFERRAL_BONUS_CONDITIONS
        if value not in REFERRAL_BONUS_CONDITIONS:
            await message.answer(f"Допустимые значения: {', '.join(REFERRAL_BONUS_CONDITIONS)}")
            return
    else:
        from referral_bot.config import MAX_SETTING_VALUE
        parsed = parse_non_negative_int(value, max_value=MAX_SETTING_VALUE)
        if parsed is None:
            await message.answer(f"Введите целое число (от 0 до {MAX_SETTING_VALUE}).")
            return
        value = str(parsed)

    db.set_setting(key, value)
    await state.clear()
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
    await message.answer(f"\u2705 \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0430!\n\n{text}", reply_markup=settings_keyboard())


@router.callback_query(F.data == "adm:settings_reset")
async def cb_admin_settings_reset(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u043e\u0432.", show_alert=True)
        return
    db.reset_settings()
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
    await callback.message.edit_text(f"\U0001f504 \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0441\u0431\u0440\u043e\u0448\u0435\u043d\u044b \u043a \u0434\u0435\u0444\u043e\u043b\u0442\u0430\u043c!\n\n{text}", reply_markup=settings_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("uwd:"))
async def cb_user_withdrawals_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    page = parse_positive_int(parts[1]) if len(parts) > 1 else None
    if page is None:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    user_id = callback.from_user.id
    withdrawals, total_pages = db.get_user_withdrawals_page(user_id, page)

    if not withdrawals:
        await callback.message.edit_text("У тебя нет заявок на вывод.")
        await callback.answer()
        return

    statuses = {
        "pending": "ожидает",
        "approved": "одобрена",
        "rejected": "отклонена",
    }
    lines = [f"\U0001f4b8 Твои заявки (стр. {page}/{total_pages}):\n"]
    for w in withdrawals:
        status = statuses.get(w["status"], w["status"])
        date = w["created_at"][:10]
        comment = f" ({w['admin_comment']})" if w["admin_comment"] else ""
        lines.append(f"  #{w['id']} {date} — {w['amount']} — {status}{comment}")

    kb = user_withdrawals_page_keyboard(page, total_pages)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("uhist:"))
async def cb_user_history_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    page = parse_positive_int(parts[1]) if len(parts) > 1 else None
    if page is None:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    user_id = callback.from_user.id
    user = db.get_user(user_id)
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start.", show_alert=True)
        return

    txs, total_pages = db.get_user_transactions_page(user_id, page)
    if not txs:
        await callback.answer("У тебя пока нет транзакций на этой странице.")
        return

    lines = [f"\U0001f4b3 \u0418\u0441\u0442\u043e\u0440\u0438\u044f (\u0441\u0442\u0440. {page}/{total_pages}):\n"]
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        date = tx["created_at"][:10]
        lines.append(f"  {date} {sign}{tx['amount']} \u2014 {tx['reason']}")

    kb = user_history_page_keyboard_user(user_id, page, total_pages)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("upart:"))
async def cb_user_partners_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    page = parse_positive_int(parts[1]) if len(parts) > 1 else None
    if page is None:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    user_id = callback.from_user.id
    user = db.get_user(user_id)
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start.", show_alert=True)
        return

    refs, total_pages = db.get_user_referrals_page(user_id, page)
    if not refs:
        await callback.answer("Нет приглашённых на этой странице.")
        return

    lines = [f"\U0001f465 \u0422\u0432\u043e\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0451\u043d\u043d\u044b\u0435 (\u0441\u0442\u0440. {page}/{total_pages}):\n"]
    for ref in refs:
        name = ref["first_name"] or ref["username"] or str(ref["user_id"])
        status = "\u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d" if ref["reward_status"] == "confirmed" else "\u043e\u0436\u0438\u0434\u0430\u0435\u0442"
        lines.append(f"  {name} \u2014 {status}")

    kb = user_partners_page_keyboard(page, total_pages)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
