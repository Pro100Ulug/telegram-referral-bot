from referral_bot.database import database as db


def get_balance(user_id: int):
    return db.get_user(user_id)


def collect_daily(user_id: int):
    return db.collect_daily_atomic(user_id)


def get_top_users(limit: int = 10):
    return db.get_top_users(limit)


def get_transactions(user_id: int, limit: int = 20):
    return db.get_transactions(user_id, limit)
