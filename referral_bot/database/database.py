import sqlite3
from datetime import datetime, timedelta, timezone

from referral_bot.config import DB_PATH, MIN_WITHDRAW_AMOUNT as DEFAULT_MIN_WITHDRAW, calculate_level


def utcnow():
    """Naive UTC timestamp, consistent across the app and with SQLite 'now'."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db():
    from referral_bot.database.migrations import run_migrations

    conn = get_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referred_by INTEGER,
                coins INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                last_collect_at TEXT,
                registered_at TEXT,
                FOREIGN KEY (referred_by) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL UNIQUE,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                confirmed_by INTEGER,
                created_at TEXT,
                confirmed_at TEXT,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                details TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                processed_by INTEGER,
                processed_at TEXT,
                admin_comment TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_rewards_referrer_status ON referral_rewards(referrer_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_withdrawals_status_user ON withdrawals(status, user_id)")

        cursor.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] == 0:
            now = utcnow().isoformat()
            for key, value in DEFAULT_SETTINGS.items():
                cursor.execute(
                    "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, now),
                )

        conn.commit()
    finally:
        conn.close()
    run_migrations()


def add_user(user_id, username, first_name, referred_by=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by, coins, level, registered_at) "
            "VALUES (?, ?, ?, ?, 0, 1, ?)",
            (user_id, username, first_name, referred_by, utcnow().isoformat()),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_user(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_balance_transaction(user_id, amount, tx_type, reason):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return False

        new_coins = row[0] + amount
        if new_coins < 0:
            conn.execute("ROLLBACK")
            return False
        new_level = calculate_level(new_coins)
        now = utcnow().isoformat()

        cursor.execute(
            "UPDATE users SET coins = coins + ?, level = ? WHERE user_id = ?",
            (amount, new_level, user_id),
        )
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, tx_type, reason, now),
        )

        conn.commit()
        return True
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_top_users(limit=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY coins DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_total_users():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        return count
    finally:
        conn.close()


def get_transactions(user_id, limit=20):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_referral_reward(referrer_id, referred_user_id, amount):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO referral_rewards "
            "(referrer_id, referred_user_id, amount, status, created_at) "
            "SELECT ?, ?, ?, 'pending', ? WHERE ? <> ?",
            (
                referrer_id,
                referred_user_id,
                amount,
                utcnow().isoformat(),
                referrer_id,
                referred_user_id,
            ),
        )
        conn.commit()
        affected = cursor.rowcount
        return affected > 0
    finally:
        conn.close()


def confirm_referral_reward_atomic(referred_user_id, confirmed_by):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            "SELECT * FROM referral_rewards WHERE referred_user_id = ? AND status = 'pending'",
            (referred_user_id,),
        )
        reward = cursor.fetchone()
        if not reward:
            conn.execute("ROLLBACK")
            return None

        reward = dict(reward)
        now = utcnow().isoformat()

        cursor.execute(
            "UPDATE referral_rewards SET status = 'confirmed', confirmed_by = ?, confirmed_at = ? WHERE id = ?",
            (confirmed_by, now, reward["id"]),
        )

        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (reward["referrer_id"],))
        ref_row = cursor.fetchone()
        if not ref_row:
            conn.execute("ROLLBACK")
            return None

        new_coins = ref_row[0] + reward["amount"]
        new_level = calculate_level(new_coins)
        cursor.execute(
            "UPDATE users SET coins = coins + ?, level = ? WHERE user_id = ?",
            (reward["amount"], new_level, reward["referrer_id"]),
        )

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (reward["referrer_id"], reward["amount"], "credit",
             "Реферальный бонус за пользователя " + str(referred_user_id), now),
        )

        conn.commit()
        return reward
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def is_reward_pending(referred_user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM referral_rewards WHERE referred_user_id = ? AND status = 'pending'",
            (referred_user_id,),
        )
        exists = cursor.fetchone() is not None
        return exists
    finally:
        conn.close()


def get_pending_rewards():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rr.*, u.first_name, u.username "
            "FROM referral_rewards rr "
            "JOIN users u ON rr.referred_user_id = u.user_id "
            "WHERE rr.status = 'pending'"
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def collect_daily_atomic(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key = 'daily_reward_base'")
        row = cursor.fetchone()
        daily_reward_base = int(row[0]) if row else 2

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.execute("ROLLBACK")
            return None, "user_not_found"

        user = dict(user)
        if user["last_collect_at"]:
            last = datetime.fromisoformat(user["last_collect_at"])
            if utcnow() - last < timedelta(hours=24):
                conn.execute("ROLLBACK")
                return None, "too_early"

        level = calculate_level(user["coins"])
        reward = level * daily_reward_base
        now = utcnow().isoformat()
        new_coins = user["coins"] + reward
        new_level = calculate_level(new_coins)

        cursor.execute(
            "UPDATE users SET coins = coins + ?, level = ?, last_collect_at = ? WHERE user_id = ?",
            (reward, new_level, now, user_id),
        )

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, reward, "credit", "Ежедневная награда", now),
        )

        conn.commit()
        return {"reward": reward, "coins": new_coins, "level": new_level}, "ok"
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def create_withdrawal(user_id, amount, details):
    min_withdraw = int(get_setting("min_withdraw_amount") or DEFAULT_MIN_WITHDRAW)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        if amount <= 0:
            conn.execute("ROLLBACK")
            return None, "invalid_amount"

        if amount < min_withdraw:
            conn.execute("ROLLBACK")
            return None, "min_amount"

        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None, "user_not_found"

        coins = row[0]
        if coins < amount:
            conn.execute("ROLLBACK")
            return None, "insufficient_balance"

        cursor.execute(
            "SELECT id FROM withdrawals WHERE user_id = ? AND status = 'pending' LIMIT 1",
            (user_id,),
        )
        if cursor.fetchone():
            conn.execute("ROLLBACK")
            return None, "already_pending"

        now = utcnow().isoformat()
        new_coins = coins - amount
        new_level = calculate_level(new_coins)

        cursor.execute(
            "UPDATE users SET coins = ?, level = ? WHERE user_id = ?",
            (new_coins, new_level, user_id),
        )

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, -amount, "debit", "Заявка на вывод", now),
        )

        cursor.execute(
            "INSERT INTO withdrawals (user_id, amount, details, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (user_id, amount, details, now),
        )

        withdrawal_id = cursor.lastrowid
        conn.commit()
        return {"id": withdrawal_id, "amount": amount, "coins": new_coins}, "ok"
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_user_withdrawals(user_id, limit=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_withdrawals_page(user_id, page=1, per_page=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE user_id = ?", (user_id,))
        total = cursor.fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cursor.execute(
            "SELECT * FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        return rows, total_pages
    finally:
        conn.close()


def has_pending_withdrawal(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM withdrawals WHERE user_id = ? AND status = 'pending' LIMIT 1",
            (user_id,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def get_pending_withdrawals():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT w.*, u.first_name, u.username "
            "FROM withdrawals w "
            "JOIN users u ON w.user_id = u.user_id "
            "WHERE w.status = 'pending' "
            "ORDER BY w.created_at ASC"
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve_withdrawal(withdrawal_id, admin_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT * FROM withdrawals WHERE id = ? AND status = 'pending'", (withdrawal_id,))
        w = cursor.fetchone()
        if not w:
            conn.execute("ROLLBACK")
            return None

        now = utcnow().isoformat()

        cursor.execute(
            "UPDATE withdrawals SET status = 'approved', processed_by = ?, processed_at = ? WHERE id = ?",
            (admin_id, now, withdrawal_id),
        )

        cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,))
        w = dict(cursor.fetchone())

        conn.commit()
        return w
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def reject_withdrawal(withdrawal_id, admin_id, comment=""):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT * FROM withdrawals WHERE id = ? AND status = 'pending'", (withdrawal_id,))
        w = cursor.fetchone()
        if not w:
            conn.execute("ROLLBACK")
            return None

        w = dict(w)
        now = utcnow().isoformat()

        cursor.execute(
            "UPDATE withdrawals SET status = 'rejected', processed_by = ?, processed_at = ?, admin_comment = ? WHERE id = ?",
            (admin_id, now, comment, withdrawal_id),
        )

        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (w["user_id"],))
        row = cursor.fetchone()
        if row:
            new_coins = row[0] + w["amount"]
            new_level = calculate_level(new_coins)
            cursor.execute(
                "UPDATE users SET coins = coins + ?, level = ? WHERE user_id = ?",
                (w["amount"], new_level, w["user_id"]),
            )

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (w["user_id"], w["amount"], "credit", "Возврат за отменённую заявку #" + str(withdrawal_id), now),
        )

        cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,))
        w = dict(cursor.fetchone())

        conn.commit()
        return w
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def log_user_action(user_id, action, details=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_actions (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (user_id, action, details, utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_actions(user_id, limit=100):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM user_actions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def check_rate_limit(user_id, action, limit, seconds):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cutoff = (utcnow() - timedelta(seconds=seconds)).isoformat()
        cursor.execute(
            "SELECT COUNT(*) FROM user_actions WHERE user_id = ? AND action = ? AND created_at >= ?",
            (user_id, action, cutoff),
        )
        count = cursor.fetchone()[0]
        return count < limit
    finally:
        conn.close()


def consume_rate_limit(user_id, action, limit, seconds, details=None):
    """Atomically count recent actions for (user, action) and record a new one.

    Returns True (and records the action) when within the limit, False when the
    limit is already reached. The check and the insert happen in a single
    transaction, so concurrent requests cannot all pass the counter.

    For a user that is not present in the users table the action cannot be
    recorded (FK) and True is returned so the caller can proceed safely.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cutoff = (utcnow() - timedelta(seconds=seconds)).isoformat()
        cursor.execute(
            "SELECT COUNT(*) FROM user_actions WHERE user_id = ? AND action = ? AND created_at >= ?",
            (user_id, action, cutoff),
        )
        count = cursor.fetchone()[0]
        if count >= limit:
            conn.execute("ROLLBACK")
            return False
        try:
            cursor.execute(
                "INSERT INTO user_actions (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
                (user_id, action, details, utcnow().isoformat()),
            )
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return True
        conn.commit()
        return True
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


DEFAULT_SETTINGS = {
    "referral_bonus": "5",
    "daily_reward_base": "2",
    "min_withdraw_amount": "50",
    "referral_bonus_condition": "none",
}

REFERRAL_BONUS_CONDITIONS = ("none", "hours_24", "active", "daily_collect")


def check_referral_bonus_condition(user_id):
    condition = get_setting("referral_bonus_condition")
    if condition == "none":
        return True

    user = get_user(user_id)
    if not user:
        return False

    if condition == "hours_24":
        registered = datetime.fromisoformat(user["registered_at"])
        return utcnow() - registered >= timedelta(hours=24)

    if condition == "active":
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM user_actions WHERE user_id = ? LIMIT 1",
                (user_id,),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    if condition == "daily_collect":
        return user["last_collect_at"] is not None

    return True


def get_setting(key):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return DEFAULT_SETTINGS.get(key)
    finally:
        conn.close()


def get_all_settings():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        result = dict(DEFAULT_SETTINGS)
        for row in rows:
            result[row[0]] = row[1]
        return result
    finally:
        conn.close()


def set_setting(key, value):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?",
            (key, value, utcnow().isoformat(), value, utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def reset_settings():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM settings")
        now = utcnow().isoformat()
        for key, value in DEFAULT_SETTINGS.items():
            cursor.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
        conn.commit()
    finally:
        conn.close()


def get_users_page(page, per_page=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cursor.execute(
            "SELECT * FROM users ORDER BY registered_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        return rows, total_pages
    finally:
        conn.close()


def get_user_referrals_page(user_id, page, per_page=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        total = cursor.fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cursor.execute(
            "SELECT u.*, rr.status as reward_status "
            "FROM users u "
            "LEFT JOIN referral_rewards rr ON u.user_id = rr.referred_user_id "
            "WHERE u.referred_by = ? "
            "ORDER BY u.registered_at DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        return rows, total_pages
    finally:
        conn.close()


def get_user_transactions_page(user_id, page, per_page=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ?", (user_id,))
        total = cursor.fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cursor.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        return rows, total_pages
    finally:
        conn.close()


def get_pending_withdrawals_page(page, per_page=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
        total = cursor.fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        cursor.execute(
            "SELECT w.*, u.first_name, u.username "
            "FROM withdrawals w "
            "JOIN users u ON w.user_id = u.user_id "
            "WHERE w.status = 'pending' "
            "ORDER BY w.created_at ASC LIMIT ? OFFSET ?",
            (per_page, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        return rows, total_pages
    finally:
        conn.close()


def get_total_coins():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(coins), 0) FROM users")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_users_count_since(days):
    cutoff = (utcnow() - timedelta(days=days)).isoformat()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= ?",
            (cutoff,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_active_users_count():
    cutoff = (utcnow() - timedelta(days=1)).isoformat()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE last_collect_at >= ?",
            (cutoff,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_withdrawals_stats():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, COUNT(*), COALESCE(SUM(amount), 0) "
            "FROM withdrawals GROUP BY status"
        )
        rows = cursor.fetchall()
        return {row[0]: {"count": row[1], "sum": row[2]} for row in rows}
    finally:
        conn.close()


def get_recent_users(limit=10):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY registered_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
