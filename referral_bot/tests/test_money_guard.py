"""CR-02: Money-logic regression tests (atomicity, concurrency, idempotency, ledger)."""

import os
import sys
import tempfile
import threading

import referral_bot.config as config

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
config.DB_PATH = _tmp.name

from referral_bot.database import database as db
from referral_bot.services import referral_service
from referral_bot.config import MIN_WITHDRAW_AMOUNT

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


def run_in_threads(fn, n=2, barrier=None):
    thr_barrier = barrier or threading.Barrier(n)
    results = []
    errors = []

    def wrapped():
        thr_barrier.wait()
        try:
            results.append(fn())
        except Exception as e:
            errors.append(repr(e))

    threads = [threading.Thread(target=wrapped) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, errors


def balance_of(user_id):
    u = db.get_user(user_id)
    return u["coins"] if u else None


def ledger_sum(user_id):
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def test_balance_edge_cases():
    section("1. БАЛАНС: ГРАНИЧНЫЕ ЗНАЧЕНИЯ")
    setup_fresh_db()
    db.add_user(101, "b", "B", None)

    ok = db.add_balance_transaction(101, 0, "credit", "zero")
    check("credit 0 -> True", ok is True)
    check("баланс после 0 = 0", balance_of(101) == 0)

    ok = db.add_balance_transaction(101, 100, "credit", "seed")
    check("credit 100 -> True", ok is True)

    ok = db.add_balance_transaction(101, 0, "debit", "zero2")
    check("debit 0 -> True", ok is True)
    check("баланс = 100", balance_of(101) == 100)

    ok = db.add_balance_transaction(101, -101, "debit", "over")
    check("debit сверх баланса (-101) -> False", ok is False)
    check("баланс не отрицательный = 100", balance_of(101) == 100)

    ok = db.add_balance_transaction(101, -100, "debit", "full")
    check("debit ровно баланс (-100) -> True", ok is True)
    check("баланс = 0", balance_of(101) == 0)

    ok = db.add_balance_transaction(101, -1, "debit", "neg_at_zero")
    check("debit -1 при 0 -> False", ok is False)

    huge = 2_000_000_000_000
    ok = db.add_balance_transaction(101, huge, "credit", "huge")
    check("credit huge -> True", ok is True)
    check("баланс = huge", balance_of(101) == huge)


def test_balance_concurrent_debit():
    section("2. БАЛАНС: ПАРАЛЛЕЛЬНЫЙ ДЕБИТ")
    setup_fresh_db()
    db.add_user(201, "c", "C", None)
    db.add_balance_transaction(201, 100, "credit", "seed")

    results, errors = run_in_threads(
        lambda: db.add_balance_transaction(201, -60, "debit", "race")
    )
    check("нет исключений", errors == [])
    successes = sum(1 for r in results if r is True)
    check("ровно одно списание успешно", successes == 1, str(results))
    check("баланс = 40, не отрицательный", balance_of(201) == 40)


def test_withdrawal_parallel_idempotent():
    section("3. ВЫВОД: ПАРАЛЛЕЛЬНЫЕ ЗАЯВКИ")
    setup_fresh_db()
    db.add_user(301, "w1", "W1", None)
    db.add_balance_transaction(301, 200, "credit", "seed")

    results, errors = run_in_threads(
        lambda: db.create_withdrawal(301, 100, "Card 7777")[1]
    )
    check("нет исключений", errors == [])
    check("ровно одна операция успешна", results.count("ok") == 1, str(results))
    check("вторая отклонена как already_pending",
          "already_pending" in results, str(results))
    wds = db.get_user_withdrawals(301)
    pending = [w for w in wds if w["status"] == "pending"]
    check("создана ровно одна pending-заявка", len(pending) == 1, str(len(pending)))
    check("баланс = 100", balance_of(301) == 100)
    check("баланс не отрицательный", balance_of(301) >= 0)


def test_withdrawal_parallel_insufficient():
    section("4. ВЫВОД: ПАРАЛЛЕЛЬНЫЕ ЗАЯВКИ (баланса на 2 не хватит)")
    setup_fresh_db()
    db.add_user(302, "w2", "W2", None)
    db.add_balance_transaction(302, 100, "credit", "seed")

    results, errors = run_in_threads(
        lambda: db.create_withdrawal(302, 60, "Card 7777")[1]
    )
    check("нет исключений", errors == [])
    check("ровно одна операция успешна", results.count("ok") == 1, str(results))
    bad = [s for s in results if s != "ok"]
    check("вторая не успешна", len(bad) == 1, str(results))
    check("баланс не отрицательный", balance_of(302) >= 0)
    check("баланс = 40", balance_of(302) == 40)


def test_withdrawal_state_machine():
    section("5. ВЫВОД: МАШИНА СОСТОЯНИЙ")
    setup_fresh_db()
    db.add_user(401, "s", "S", None)
    db.add_balance_transaction(401, 300, "credit", "seed")

    res, st = db.create_withdrawal(401, 100, "Card A")
    wid = res["id"]
    check("create -> ok", st == "ok")

    _, s2 = db.create_withdrawal(401, 50, "Card B")
    check("дубликат (pending уже есть) -> already_pending", s2 == "already_pending")

    r = db.approve_withdrawal(wid, 999)
    check("approve -> ok", r is not None and r["status"] == "approved")
    check("approve не меняет баланс", balance_of(401) == 200)

    r2 = db.approve_withdrawal(wid, 999)
    check("повторный approve -> None", r2 is None)

    r3 = db.reject_withdrawal(wid, 999)
    check("reject после approve -> None", r3 is None)

    be = None
    check("no duplicate credit on approve-after-reject", balance_of(401) == 200)

    # separate user: reject -> refund once; then no more transitions
    db.add_user(402, "s2", "S2", None)
    db.add_balance_transaction(402, 300, "credit", "seed")
    res2, _ = db.create_withdrawal(402, 100, "Card C")
    wid2 = res2["id"]
    rr = db.reject_withdrawal(wid2, 999, "no")
    check("reject -> ok", rr is not None and rr["status"] == "rejected")
    check("reject возвращает средства (300)", balance_of(402) == 300)

    rr2 = db.reject_withdrawal(wid2, 999)
    check("повторный reject -> None", rr2 is None)
    check("нет повторного refund (300)", balance_of(402) == 300)

    ar = db.approve_withdrawal(wid2, 999)
    check("approve после reject -> None", ar is None)
    check("баланс остаётся 300", balance_of(402) == 300)


def test_withdrawal_amount_validation():
    section("6. ВЫВОД: ВАЛИДАЦИЯ СУММ")
    setup_fresh_db()
    db.add_user(501, "v", "V", None)
    db.add_balance_transaction(501, 1_000_000, "credit", "seed")

    _, s = db.create_withdrawal(501, 0, "x")
    check("amount=0 -> invalid_amount", s == "invalid_amount")

    _, s = db.create_withdrawal(501, -1, "x")
    check("amount=-1 -> invalid_amount", s == "invalid_amount")

    _, s = db.create_withdrawal(501, MIN_WITHDRAW_AMOUNT - 1, "x")
    check("amount=MIN-1 -> min_amount", s == "min_amount")

    _, s = db.create_withdrawal(501, -MIN_WITHDRAW_AMOUNT - 100, "x")
    check("amount=-MIN-100 -> invalid_amount", s == "invalid_amount")

    res, s = db.create_withdrawal(501, MIN_WITHDRAW_AMOUNT, "x")
    check("amount=MIN -> ok", s == "ok")
    db.approve_withdrawal(res["id"], 999)

    res, s = db.create_withdrawal(501, MIN_WITHDRAW_AMOUNT + 1, "x")
    check("amount=MIN+1 -> ok", s == "ok")
    db.approve_withdrawal(res["id"], 999)

    res, s = db.create_withdrawal(501, 10_000, "x")
    check("very large (весь баланс) -> ok", s == "ok")
    db.approve_withdrawal(res["id"], 999)

    _, s = db.create_withdrawal(501, 10**15, "x")
    check("amount=10^15 (сверх баланса) -> insufficient_balance", s == "insufficient_balance")

    db.add_user(502, "v2", "V2", None)
    _, s = db.create_withdrawal(502, 50, "x")
    check("нет баланса -> insufficient_balance", s == "insufficient_balance")

    _, s = db.create_withdrawal(999999, 50, "x")
    check("пользователь не найден -> user_not_found", s == "user_not_found")


def test_referral_guards():
    section("7. РЕФЕРАЛ: ЗАЩИТЫ")
    setup_fresh_db()
    db.add_user(601, "ref", "Ref", None)
    db.add_user(602, "new", "New", None)

    check("self-referral отклонён",
          referral_service.validate_referrer(601, 601) is False)
    check("несуществующий реферер отклонён",
          referral_service.validate_referrer(999999, 602) is False)
    check("валидный реферер принят",
          referral_service.validate_referrer(601, 602) is True)

    r1 = db.create_referral_reward(601, 602, 5)
    r2 = db.create_referral_reward(601, 602, 5)
    check("повторная награда (UNIQUE) -> False", r2 is False and r1 is True)

    check("self-referral на уровне DB отклонён",
          db.create_referral_reward(601, 601, 5) is False)

    from sqlite3 import IntegrityError
    raised = False
    try:
        db.create_referral_reward(999999, 602, 5)
    except IntegrityError:
        raised = True
    check("несуществующий реферер отклонён (FK, OR IGNORE -> False)",
          raised or db.create_referral_reward(999999, 602, 5) is False)

    conn = db.get_connection()
    try:
        dangling = conn.execute(
            "SELECT COUNT(*) FROM referral_rewards WHERE referrer_id = ?",
            (999999,),
        ).fetchone()[0]
    finally:
        conn.close()
    check("no dangling row for non-existent referrer", dangling == 0)


def test_referral_concurrent_confirm():
    section("8. РЕФЕРАЛ: ПАРАЛЛЕЛЬНОЕ ПОДТВЕРЖДЕНИЕ")
    setup_fresh_db()
    db.add_user(701, "ref", "Ref", None)
    db.add_user(702, "new", "New", None)
    created = db.create_referral_reward(701, 702, 5)
    check("награда создана", created is True)

    results, errors = run_in_threads(
        lambda: db.confirm_referral_reward_atomic(702, 999) is not None
    )
    check("нет исключений", errors == [])
    check("ровно одно начисление", sum(1 for r in results if r) == 1, str(results))
    check("реферер получил 5 монет (один раз)", balance_of(701) == 5)
    check("награда больше не pending",
          db.is_reward_pending(702) is False)
    txs = db.get_transactions(701)
    credit_txs = [t for t in txs if t["type"] == "credit" and "Реферальный" in t["reason"]]
    check("в ledger ровно одна credit-транзакция реферала", len(credit_txs) == 1,
          str(len(credit_txs)))


def test_daily_reward_concurrent():
    section("9. ЕЖЕДНЕВНАЯ НАГРАДА: ПАРАЛЛЕЛЬНЫЙ СБОР")
    setup_fresh_db()
    db.add_user(801, "d", "D", None)

    results, errors = run_in_threads(
        lambda: db.collect_daily_atomic(801)[1]
    )
    check("нет исключений", errors == [])
    check("ровно один сбор успешен", results.count("ok") == 1, str(results))
    check("второй -> too_early", "too_early" in results, str(results))
    check("reward засчитан один раз", balance_of(801) == 2)

    r, s = db.collect_daily_atomic(801)
    check("повторный сбор -> too_early", s == "too_early")
    check("баланс не удвоился", balance_of(801) == 2)

    db.add_user(802, "d2", "D2", None)
    r2, s2 = db.collect_daily_atomic(999999)
    check("несуществующий user -> user_not_found", s2 == "user_not_found")


def test_registration_concurrent():
    section("10. РЕГИСТРАЦИЯ: ПАРАЛЛЕЛЬНАЯ")
    setup_fresh_db()
    results, errors = run_in_threads(
        lambda: db.add_user(901, "r", "R", None)
    )
    check("нет исключений", errors == [], str(errors))
    check("ровно одна регистрация успешна", sum(1 for r in results if r) == 1,
          str(results))
    check("пользователь создан", db.get_user(901) is not None)
    check("а первый вызов обычного дубликата -> False", db.add_user(901, "r", "R", None) is False)


def test_ledger_consistency():
    section("11. LEDGER: СОГЛАСОВАННОСТЬ balance = SUM(transactions)")
    setup_fresh_db()
    db.add_user(1001, "l", "L", None)
    db.add_balance_transaction(1001, 100, "credit", "seed")
    db.add_balance_transaction(1001, 50, "credit", "extra")
    res, _ = db.create_withdrawal(1001, 80, "Card")
    db.reject_withdrawal(res["id"], 999, "no")
    db.add_user(1002, "lr", "LR", 1001)
    db.create_referral_reward(1001, 1002, 5)
    db.confirm_referral_reward_atomic(1002, 999)
    db.collect_daily_atomic(1001)

    check("balance == sum(transactions)", balance_of(1001) == ledger_sum(1001),
          f"balance={balance_of(1001)} sum={ledger_sum(1001)}")
    check("balance реферера == sum", balance_of(1002) == ledger_sum(1002))


def test_admin_coins_limits():
    section("12. АДМИН: НАЧИСЛЕНИЕ (config + DB)")
    setup_fresh_db()
    from referral_bot.config import MAX_ADMIN_ADD_COINS
    check("MAX_ADMIN_ADD_COINS = 10000", MAX_ADMIN_ADD_COINS == 10000)

    db.add_user(1101, "a", "A", None)
    ok = db.add_balance_transaction(1101, MAX_ADMIN_ADD_COINS, "credit", "admin_add")
    check("admin add == MAX -> ok", ok is True and balance_of(1101) == MAX_ADMIN_ADD_COINS)

    ok = db.add_balance_transaction(1101, 20001, "credit", "admin_add2")
    check("admin add (несколько раз) корректен",
          ok is True and balance_of(1101) == MAX_ADMIN_ADD_COINS + 20001)

    ok = db.add_balance_transaction(1101, -30002, "debit", "admin_sub")
    check("admin add отрицательный сверх баланса -> False, баланс не отрицательный",
          ok is False and balance_of(1101) >= 0)
    check("баланс не изменился после rejected debit",
          balance_of(1101) == MAX_ADMIN_ADD_COINS + 20001)


def main():
    print("\n" + "=" * 60)
    print("  CR-02 MONEY GUARD TESTS")
    print("=" * 60)

    test_balance_edge_cases()
    test_balance_concurrent_debit()
    test_withdrawal_parallel_idempotent()
    test_withdrawal_parallel_insufficient()
    test_withdrawal_state_machine()
    test_withdrawal_amount_validation()
    test_referral_guards()
    test_referral_concurrent_confirm()
    test_daily_reward_concurrent()
    test_registration_concurrent()
    test_ledger_consistency()
    test_admin_coins_limits()

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