from referral_bot.database import database as db


def register_referral(referrer_id: int, referred_user_id: int) -> bool:
    bonus = int(db.get_setting("referral_bonus") or 5)
    return db.create_referral_reward(referrer_id, referred_user_id, bonus)


def confirm_reward(referred_user_id: int, confirmed_by: int):
    return db.confirm_referral_reward_atomic(referred_user_id, confirmed_by)


def get_pending_rewards():
    return db.get_pending_rewards()


def get_user_referrals(user_id: int):
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT u.*, rr.status as reward_status "
            "FROM users u "
            "LEFT JOIN referral_rewards rr ON u.user_id = rr.referred_user_id "
            "WHERE u.referred_by = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_referral_count(user_id: int) -> int:
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_confirmed_count(user_id: int) -> int:
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM referral_rewards WHERE referrer_id = ? AND status = 'confirmed'",
            (user_id,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def validate_referrer(referrer_id: int, self_id: int) -> bool:
    if referrer_id == self_id:
        return False
    user = db.get_user(referrer_id)
    return user is not None
