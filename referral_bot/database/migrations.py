from referral_bot.database.database import get_connection, DEFAULT_SETTINGS, utcnow


def run_migrations():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}

        if "last_collect_at" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_collect_at TEXT")

        if "level" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")

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
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at)")

        cursor.execute("SELECT value FROM settings WHERE key = 'referral_bonus_condition'")
        if cursor.fetchone() is None:
            now = utcnow().isoformat()
            cursor.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                ("referral_bonus_condition", "none", now),
            )

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


def _table_has_foreign_keys(conn, table):
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    return len(rows) > 0


def _rebuild_transactions_with_fk(conn):
    if _table_has_foreign_keys(conn, "transactions"):
        return False
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE transactions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute(
        "INSERT INTO transactions_new (id, user_id, amount, type, reason, created_at) "
        "SELECT id, user_id, amount, type, reason, created_at FROM transactions"
    )
    cursor.execute("DROP TABLE transactions")
    cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at)")
    return True


def _rebuild_withdrawals_with_fk(conn):
    if _table_has_foreign_keys(conn, "withdrawals"):
        return False
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE withdrawals_new (
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
    cursor.execute(
        "INSERT INTO withdrawals_new "
        "(id, user_id, amount, details, status, created_at, processed_by, processed_at, admin_comment) "
        "SELECT id, user_id, amount, details, status, created_at, processed_by, processed_at, admin_comment "
        "FROM withdrawals"
    )
    cursor.execute("DROP TABLE withdrawals")
    cursor.execute("ALTER TABLE withdrawals_new RENAME TO withdrawals")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_withdrawals_status_user ON withdrawals(status, user_id)")
    return True


def apply_foreign_key_migration():
    """Add FK constraints to legacy transactions/withdrawals tables.

    This migration is idempotent and safe only when the tables contain no
    orphan rows. It is intentionally NOT wired into run_migrations/init_db:
    apply it explicitly after verifying orphans and testing on a copy of the
    production database.
    """
    conn = get_connection()
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        changed_transactions = _rebuild_transactions_with_fk(conn)
        changed_withdrawals = _rebuild_withdrawals_with_fk(conn)
        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
        return {
            "transactions_rebuilt": changed_transactions,
            "withdrawals_rebuilt": changed_withdrawals,
            "integrity": integrity,
            "foreign_key_check_errors": len(fk_check),
        }
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()