"""Functional testing of the referral bot database layer."""

import os
import sys
import tempfile
from datetime import datetime, timedelta

import referral_bot.config as config

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
config.DB_PATH = _tmp.name

from referral_bot.database import database as db
from referral_bot.config import (
    REFERRAL_BONUS, DAILY_REWARD_BASE, MIN_WITHDRAW_AMOUNT,
    COINS_PER_LEVEL, calculate_level,
)

RESULTS = []


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    marker = "[+]" if condition else "[-]"
    line = f"  {marker} {name}"
    if detail:
        line += f"  ({detail})"
    print(line)


def setup_fresh_db():
    if os.path.exists(config.DB_PATH):
        os.unlink(config.DB_PATH)
    db.init_db()


def test_registration():
    section("1. РЕГИСТРАЦИЯ НОВОГО ПОЛЬЗОВАТЕЛЯ")
    setup_fresh_db()

    result = db.add_user(1001, "alice", "Alice", None)
    check("Регистрация нового пользователя", result is True)

    user = db.get_user(1001)
    check("Пользователь создан в БД", user is not None)
    check("user_id корректен", user["user_id"] == 1001)
    check("username корректен", user["username"] == "alice")
    check("first_name корректен", user["first_name"] == "Alice")
    check("Начальный баланс = 0", user["coins"] == 0)
    check("Начальный уровень = 1", user["level"] == 1)
    check("referred_by = None", user["referred_by"] is None)
    check("registered_at установлен", user["registered_at"] is not None)

    result2 = db.add_user(1001, "alice", "Alice", None)
    check("Повторная регистрация -> False", result2 is False)


def test_referral():
    section("2. РЕФЕРАЛ")
    setup_fresh_db()

    db.add_user(2001, "referrer_user", "Referrer", None)
    db.add_user(2002, "referred_user", "Referred", 2001)

    user2 = db.get_user(2002)
    check("referred_by установлен", user2["referred_by"] == 2001)

    created = db.create_referral_reward(2001, 2002, REFERRAL_BONUS)
    check("referral_rewards создана", created is True)

    pending = db.get_pending_rewards()
    check("Награда в pending", len(pending) == 1)
    check("status = pending", pending[0]["status"] == "pending")

    created2 = db.create_referral_reward(2001, 2002, REFERRAL_BONUS)
    check("Дублирование (IGNORE) -> False", created2 is False)


def test_bonus_accrual():
    section("3. НАЧИСЛЕНИЕ БОНУСА")
    setup_fresh_db()

    db.add_user(3001, "referrer", "Referrer", None)
    db.add_user(3002, "referred", "Referred", 3001)
    db.create_referral_reward(3001, 3002, REFERRAL_BONUS)

    reward = db.confirm_referral_reward_atomic(3002, 9999)
    check("confirm вернул награду", reward is not None)
    check("amount = REFERRAL_BONUS", reward["amount"] == REFERRAL_BONUS)

    referrer = db.get_user(3001)
    check("Баланс реферера = 5", referrer["coins"] == REFERRAL_BONUS)

    is_p = db.is_reward_pending(3002)
    check("is_reward_pending = False", is_p is False)

    reward2 = db.confirm_referral_reward_atomic(3002, 9999)
    check("Повторное подтверждение -> None", reward2 is None)


def test_daily_reward():
    section("4. ЕЖЕДНЕВНАЯ НАГРАДА")
    setup_fresh_db()

    db.add_user(4001, "daily_user", "DailyUser", None)
    result, status = db.collect_daily_atomic(4001)
    check("collect успешен", status == "ok")
    check("reward = 2", result["reward"] == DAILY_REWARD_BASE)

    result2, status2 = db.collect_daily_atomic(4001)
    check("Повторный сбор -> too_early", status2 == "too_early")

    result3, status3 = db.collect_daily_atomic(9999)
    check("Несуществующий user -> user_not_found", status3 == "user_not_found")


def test_balance_operations():
    section("5. БАЛАНС")
    setup_fresh_db()

    db.add_user(5001, "balance_user", "BalUser", None)
    ok = db.add_balance_transaction(5001, 100, "credit", "Test")
    check("credit", ok is True)

    user = db.get_user(5001)
    check("Баланс = 100", user["coins"] == 100)

    ok2 = db.add_balance_transaction(5001, -30, "debit", "Test")
    check("debit", ok2 is True)

    user2 = db.get_user(5001)
    check("Баланс = 70", user2["coins"] == 70)

    ok3 = db.add_balance_transaction(5001, -100, "debit", "Test")
    check("debit сверх баланса -> False", ok3 is False)

    top = db.get_top_users(10)
    check("get_top_users", len(top) >= 1)

    total = db.get_total_users()
    check("get_total_users", total >= 1)


def test_withdrawal():
    section("6. ВЫВОД СРЕДСТВ")
    setup_fresh_db()

    db.add_user(6001, "withdraw_user", "WUser", None)
    db.add_balance_transaction(6001, 200, "credit", "Balance")

    result, status = db.create_withdrawal(6001, 100, "Card 1234")
    check("Создание заявки", status == "ok")
    check("Баланс = 100", result["coins"] == 100)

    _, s2 = db.create_withdrawal(6001, 0, "Card")
    check("amount=0 -> invalid_amount", s2 == "invalid_amount")

    _, s3 = db.create_withdrawal(6001, 10, "Card")
    check("amount<MIN -> min_amount", s3 == "min_amount")

    _, s4 = db.create_withdrawal(6001, 500, "Card")
    check("insufficient_balance", s4 == "insufficient_balance")

    _, s5 = db.create_withdrawal(9999, 50, "Card")
    check("user_not_found", s5 == "user_not_found")


def test_admin_approve():
    section("7. ПОДТВЕРЖДЕНИЕ ВЫВОДА")
    setup_fresh_db()

    db.add_user(7001, "approve_user", "AUser", None)
    db.add_balance_transaction(7001, 200, "credit", "Balance")
    res, _ = db.create_withdrawal(7001, 100, "Card 1111")
    wid = res["id"]

    result = db.approve_withdrawal(wid, 9999)
    check("approve вернул заявку", result is not None)
    check("status = approved", result["status"] == "approved")

    result2 = db.approve_withdrawal(wid, 9999)
    check("Повторное одобрение -> None", result2 is None)


def test_admin_reject():
    section("8. ОТКЛОНЕНИЕ ВЫВОДА")
    setup_fresh_db()

    db.add_user(8001, "reject_user", "RUser", None)
    db.add_balance_transaction(8001, 200, "credit", "Balance")
    res, _ = db.create_withdrawal(8001, 100, "Card 2222")
    wid = res["id"]

    result = db.reject_withdrawal(wid, 9999, comment="Bad")
    check("reject вернул заявку", result is not None)
    check("status = rejected", result["status"] == "rejected")

    user = db.get_user(8001)
    check("Баланс возвращён = 200", user["coins"] == 200)

    result2 = db.reject_withdrawal(wid, 9999)
    check("Повторное отклонение -> None", result2 is None)


def test_error_handling():
    section("9. ОШИБКИ")
    setup_fresh_db()

    check("get_user None", db.get_user(99999) is None)
    check("get_transactions []", db.get_transactions(99999) == [])

    db.add_user(9001, "err", "Err", None)
    _, s = db.create_withdrawal(9001, 10, "Test")
    check("min_amount", s == "min_amount")


def test_levels():
    section("10. УРОВНИ")
    check("0 -> 1", calculate_level(0) == 1)
    check("49 -> 1", calculate_level(49) == 1)
    check("50 -> 2", calculate_level(50) == 2)
    check("100 -> 3", calculate_level(100) == 3)
    check("500 -> 11", calculate_level(500) == 11)


def test_referral_bonus_condition_none():
    section("11. УСЛОВИЕ: none")
    setup_fresh_db()

    db.set_setting("referral_bonus_condition", "none")
    db.add_user(11001, "referrer", "Ref", None)
    db.add_user(11002, "referred", "R", 11001)
    db.create_referral_reward(11001, 11002, 5)

    check("none: всегда True", db.check_referral_bonus_condition(11002) is True)


def test_referral_bonus_condition_daily_collect():
    section("12. УСЛОВИЕ: daily_collect")
    setup_fresh_db()

    db.set_setting("referral_bonus_condition", "daily_collect")
    db.add_user(12001, "referrer", "Ref", None)
    db.add_user(12002, "referred", "R", 12001)
    db.create_referral_reward(12001, 12002, 5)

    check("daily_collect: без collect -> False",
          db.check_referral_bonus_condition(12002) is False)

    db.collect_daily_atomic(12002)

    check("daily_collect: после collect -> True",
          db.check_referral_bonus_condition(12002) is True)


def test_referral_bonus_condition_hours_24():
    section("13. УСЛОВИЕ: hours_24")
    setup_fresh_db()

    db.set_setting("referral_bonus_condition", "hours_24")
    db.add_user(13001, "referrer", "Ref", None)
    db.add_user(13002, "referred", "R", 13001)
    db.create_referral_reward(13001, 13002, 5)

    check("hours_24: сразу -> False",
          db.check_referral_bonus_condition(13002) is False)

    conn = db.get_connection()
    try:
        old_time = (db.utcnow() - timedelta(hours=25)).isoformat()
        conn.execute("UPDATE users SET registered_at = ? WHERE user_id = ?",
                     (old_time, 13002))
        conn.commit()
    finally:
        conn.close()

    check("hours_24: после 24ч -> True",
          db.check_referral_bonus_condition(13002) is True)


def test_referral_bonus_condition_active():
    section("14. УСЛОВИЕ: active")
    setup_fresh_db()

    db.set_setting("referral_bonus_condition", "active")
    db.add_user(14001, "referrer", "Ref", None)
    db.add_user(14002, "referred", "R", 14001)
    db.create_referral_reward(14001, 14002, 5)

    check("active: без активности -> False",
          db.check_referral_bonus_condition(14002) is False)

    db.log_user_action(14002, "/start")

    check("active: после действия -> True",
          db.check_referral_bonus_condition(14002) is True)


def test_rate_limit():
    section("15. RATE LIMITING")
    setup_fresh_db()

    db.add_user(15001, "user", "U", None)

    check("rate: без действий -> True",
          db.check_rate_limit(15001, "/start", 5, 60) is True)

    for _ in range(4):
        db.log_user_action(15001, "/start")

    check("rate: 4 действия (лимит 5) -> True",
          db.check_rate_limit(15001, "/start", 5, 60) is True)

    db.log_user_action(15001, "/start")

    check("rate: 5 действий (лимит 5) -> False",
          db.check_rate_limit(15001, "/start", 5, 60) is False)

    check("rate: другое действие -> True",
          db.check_rate_limit(15001, "/collect", 3, 60) is True)


def test_action_logging():
    section("16. ЛОГИРОВАНИЕ ДЕЙСТВИЙ")
    setup_fresh_db()

    db.add_user(16001, "user", "U", None)

    actions_before = db.get_user_actions(16001)
    check("до команды: 0 действий", len(actions_before) == 0)

    db.log_user_action(16001, "/start")

    actions_after = db.get_user_actions(16001)
    check("после /start: 1 действие", len(actions_after) == 1)
    check("действие = /start", actions_after[0]["action"] == "/start")

    db.log_user_action(16001, "/collect")
    db.log_user_action(16001, "/withdraw", "amount=100")

    actions_final = db.get_user_actions(16001)
    check("после 3 команд: 3 действия", len(actions_final) == 3)


def main():
    print("\n" + "=" * 60)
    print("  ТЕСТЫ БД REFERRAL BOT")
    print("=" * 60)

    test_registration()
    test_referral()
    test_bonus_accrual()
    test_daily_reward()
    test_balance_operations()
    test_withdrawal()
    test_admin_approve()
    test_admin_reject()
    test_error_handling()
    test_levels()
    test_referral_bonus_condition_none()
    test_referral_bonus_condition_daily_collect()
    test_referral_bonus_condition_hours_24()
    test_referral_bonus_condition_active()
    test_rate_limit()
    test_action_logging()

    if os.path.exists(config.DB_PATH):
        os.unlink(config.DB_PATH)

    total = len(RESULTS)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")

    print(f"\n{'='*60}")
    print(f"  ИТОГИ: {passed}/{total} пройдено, {failed} провалено")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
