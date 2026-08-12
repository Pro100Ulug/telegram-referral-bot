from referral_bot.database import database as db


def create_withdrawal(user_id: int, amount: int, details: str):
    return db.create_withdrawal(user_id, amount, details)


def get_user_withdrawals(user_id: int, limit: int = 10):
    return db.get_user_withdrawals(user_id, limit)


def get_pending_withdrawals():
    return db.get_pending_withdrawals()


def approve_withdrawal(withdrawal_id: int, admin_id: int):
    return db.approve_withdrawal(withdrawal_id, admin_id)


def reject_withdrawal(withdrawal_id: int, admin_id: int, comment: str = ""):
    return db.reject_withdrawal(withdrawal_id, admin_id, comment)
