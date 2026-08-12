"""Tests for configurable DB_PATH (CR-01: SQLite persistence on Render)."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import referral_bot.config as config

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


def test_env_override():
    section("1. DB_PATH БЕРЁТСЯ ИЗ ENV")
    old = os.environ.get("DB_PATH")
    try:
        tmp = tempfile.mkdtemp()
        custom = str(Path(tmp) / "custom.db")
        os.environ["DB_PATH"] = custom
        got = config.get_db_path()
        check("get_db_path() возвращает путь из ENV", str(got) == str(Path(custom).resolve()), str(got))
        check("результат — это Path", isinstance(got, Path))
        check("путь абсолютный", got.is_absolute())
    finally:
        if old is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old


def test_fallback():
    section("2. FALLBACK БЕЗ ENV")
    old = os.environ.get("DB_PATH")
    try:
        os.environ.pop("DB_PATH", None)
        expected = config.BASE_DIR / "referral_bot.db"
        got = config.get_db_path()
        check("fallback == BASE_DIR/referral_bot.db", got == expected, str(got))
        check("fallback — это Path", isinstance(got, Path))
        check("fallback абсолютный", got.is_absolute())
    finally:
        if old is not None:
            os.environ["DB_PATH"] = old


def test_module_default():
    section("3. МОДУЛЬНАЯ КОНСТАНТА DB_PATH")
    check("config.DB_PATH == BASE_DIR/referral_bot.db",
          config.DB_PATH == config.BASE_DIR / "referral_bot.db", str(config.DB_PATH))


def test_existing_db_intact():
    section("4. СУЩЕСТВУЮЩАЯ БД НЕ ЛОМАЕТСЯ")
    db_path = config.DB_PATH
    check("БД существует", db_path.exists(), str(db_path))
    if not db_path.exists():
        return
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        check("integrity_check == ok", integrity == "ok", integrity)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("users", "transactions", "referral_rewards", "withdrawals", "settings", "user_actions"):
            check(f"таблица {t} существует", t in tables)
    finally:
        conn.close()


def test_env_equals_module():
    section("5. ENV ПРИОРИТЕТНЕЕ FALLBACK")
    old = os.environ.get("DB_PATH")
    try:
        tmp = tempfile.mkdtemp()
        custom = str(Path(tmp) / "from_env.db")
        os.environ["DB_PATH"] = custom
        got = config.get_db_path()
        fallback = config.BASE_DIR / "referral_bot.db"
        check("при заданном ENV путь НЕ равен fallback", got != fallback, str(got))
        check("путь равен ENV-значению", str(got) == str(Path(custom).resolve()))
    finally:
        if old is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old


def main():
    print("\n" + "=" * 60)
    print("  ТЕСТЫ DB_PATH (CR-01)")
    print("=" * 60)

    test_env_override()
    test_fallback()
    test_module_default()
    test_existing_db_intact()
    test_env_equals_module()

    total = len(RESULTS)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")

    print(f"\n{'='*60}")
    print(f"  ИТОГИ: {passed}/{total} пройдено, {failed} провалено")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
