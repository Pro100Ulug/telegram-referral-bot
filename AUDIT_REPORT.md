# AUDIT REPORT — telegram-referral-bot

Date: 2026-08-12
Scope: full read-only audit of `referral_bot/`, config, database, services, handlers, keyboards, middlewares, tests, deployment files.
Method: static code review, SQLite schema inspection of the live DB, execution of the complete test suite.

---

## Executive Summary

The project is a Telegram referral bot built on **aiogram 3.x** with **SQLite** (WAL) persistence. The core money logic is implemented carefully: every balance mutation is wrapped in `BEGIN IMMEDIATE` transactions with explicit rollback, balances cannot go negative through application paths, referral bonuses are idempotent (UNIQUE + status guard), withdrawals are single-flight (pending guard inside the transaction), and the ledger invariant `balance == SUM(transactions)` holds (verified by an executed test).

The complete test suite was executed: **164/164 PASS** (test_database 67, test_money_guard 80, test_db_path 17).

No CRITICAL vulnerabilities were confirmed. The main issues are:

1. **HIGH — HTML injection / message-breaking** via unescaped user-controlled text rendered with global `parse_mode="HTML"`.
2. **HIGH — schema drift**: the deployed/live database has **no foreign keys**; the FK migration (`apply_foreign_key_migration`) is not wired into `run_migrations`, so tests (which run on fresh FK-enabled DBs) do not reflect the real deployed schema. Referential integrity depends entirely on application code.
3. **MEDIUM — non-atomic rate-limit check-then-log** for `/start` and `/withdraw`, and unbounded growth of `user_actions`.
4. **MEDIUM — missing audit trail** for sensitive admin financial actions (approve / reject / confirm).
5. Several LOW/INFO hardening items.

No production code was modified during this audit.

---

## Architecture

```
Telegram update
  → aiogram Dispatcher (MemoryStorage FSM)
    → middlewares (AutoRegister, CallbackLogger/rate-limit)
      → routers: start, profile, referral, wallet, withdrawal, admin, help, callbacks
        → services (referral_service, wallet_service, withdrawal_service)
          → database (database.py, migrations.py)
            → SQLite (referral_bot.db, WAL mode)
```

- Entry point: `referral_bot/main.py` → `python -m referral_bot.main`
- Global HTML parse mode configured in `main.py:35`.
- DB init: `init_db()` (creates schema) then `run_migrations()` (idempotent ALTERs / seed settings).
- Balance mutations (complete map):
  | Mutation | Trigger | Atomic | Validation |
  |---|---|---|---|
  | `add_balance_transaction` | admin `/addcoins` | BEGIN IMMEDIATE | result balance >= 0 |
  | `confirm_referral_reward_atomic` | admin `/confirm` | BEGIN IMMEDIATE | status='pending' + UNIQUE(referred_user_id) |
  | `collect_daily_atomic` | user `/collect` | BEGIN IMMEDIATE | 24h window (inside txn) |
  | `create_withdrawal` | user `/withdraw` | BEGIN IMMEDIATE | amount>0, >=min, balance, no pending (all inside txn) |
  | `reject_withdrawal` | admin `/reject` | BEGIN IMMEDIATE | status='pending' → exact refund + ledger credit |
  | `approve_withdrawal` | admin `/approve` | BEGIN IMMEDIATE | status='pending' (no money movement; deducted at request) |

## Repository Inventory

```
referral_bot/
  main.py, config.py
  database/{__init__.py, database.py, migrations.py}
  handlers/{start,profile,referral,wallet,withdrawal,admin,help,callbacks}.py
  services/{referral_service,wallet_service,withdrawal_service}.py
  keyboards/{menus.py, admin_panel.py}
  middlewares/__init__.py
  utils/{security.py}
  tests/{test_database,test_money_guard,test_db_path}.py
Dockerfile, render.yaml, requirements.txt, .env.example, .gitignore, .dockerignore
backup_old_version/   (excluded from Git; legacy code, not audited as production)
```

## Configuration Audit

- `config.py` loads `.env` via `load_dotenv(BASE_DIR / ".env")`; missing file is ignored (Render provides env vars).
- `BOT_TOKEN`: empty → `RuntimeError` at startup. Correct.
- `ADMIN_IDS`: parsed as comma-separated ints; malformed env value raises `ValueError` at import (fails fast — acceptable, but unvalidated).
- `PROXY_URL`: optional.
- `DB_PATH`: env override → `Path.expanduser().resolve()`, fallback `BASE_DIR/referral_bot.db`. Correct (CR-01 covered by tests).
- Financial constants: `REFERRAL_BONUS=5` is **unused dead constant** (real value read from `settings` table); `MIN_WITHDRAW_AMOUNT` used only as fallback. INFO.
- No secrets are read, logged, or committed. `.env` is gitignored and not copied by Docker.

## Database Audit

Schema (live DB verified): `users`, `transactions`, `referral_rewards`, `withdrawals`, `settings`, `user_actions`.
- Unique constraint present on `referral_rewards.referred_user_id` (verified `sqlite_autoindex_referral_rewards_1`).
- WAL journal mode active (verified on live DB).
- `busy_timeout=10000`, `timeout=30`.
- **Foreign keys: NOT present in the live database** (`PRAGMA foreign_key_list` empty for transactions, withdrawals, referral_rewards, users, user_actions). `init_db` declares FKs in DDL for fresh DBs, but `CREATE TABLE IF NOT EXISTS` does not alter existing tables; `apply_foreign_key_migration` (in `migrations.py`) rebuilds transactions/withdrawals with FKs but is **not called** by `run_migrations`. See H2.
- All write paths use `BEGIN IMMEDIATE` (single-writer serialization) with `ROLLBACK` on exception and in every early-return branch.
- Read paths open a fresh connection per call (correct for SQLite thread-safety, small overhead).
- No DB-level CHECK constraints (e.g., `coins >= 0`, `amount > 0`, `status IN (...)`). See M4.

## Financial / Balance Audit

Verified invariants (with executed tests):
- Balance never negative through application paths. ✅ (money_guard §1, §2, §12)
- Referral bonus credited exactly once. ✅ (UNIQUE + status; money_guard §8)
- Withdrawal deducted exactly once. ✅ (money_guard §3, §4, §5)
- Rejected withdrawal refunds exactly the reserved amount. ✅ (money_guard §5)
- `balance == SUM(transactions)` per user. ✅ (money_guard §11)
- Concurrency: parallel debit / parallel withdrawal / parallel referral confirm / parallel daily collect / parallel registration all result in exactly one success. ✅
- Integer arithmetic only (no floats) — no precision issues.
- Amount input: user-supplied amounts parsed via strict `parse_positive_int` (ASCII digits, bounded, rejects >40-char strings, rejects bool/None). Negative and zero blocked at DB layer. ✅

No money-creation/destruction bug confirmed.

## Referral Audit

- Referrer = user_id embedded in deep-link payload, parsed via `parse_telegram_id`, validated by `validate_referrer` (self-referral blocked, referrer must exist).
- Bonus row created only for a **newly inserted** user (`is_new`), so repeated `/start` cannot create duplicates.
- DB enforces UNIQUE(referred_user_id) and `WHERE referrer_id <> referred_user_id`.
- Confirm is atomic and idempotent. Condition (`none/hours_24/active/daily_collect`) enforced at admin confirm time.
- **Circular referral (A→B and B→A) is possible** — each gets a reward when the other is confirmed. Not blocked. Acceptable product decision, but note it enables mutual farming (admins control confirm).

## Withdrawal Audit

- Full lifecycle trace: request → atomic validation (amount, min, balance, no-pending) → deduction + ledger debit → pending row → admin approve/reject → refund on reject (exact amount, ledger credit).
- Double-withdrawal, double-approve, double-reject, approve-after-reject all guarded by `status='pending'` inside the transaction. Tests confirm.
- Notifications to user are best-effort (`except Exception: pass`).
- Admin action not logged to `user_actions` (see M2).

## Telegram Security Audit

- User identity always taken from `event.from_user.id` / `callback.from_user.id` (server-provided, not client-supplied). ✅
- All admin command handlers check `is_admin()`. ✅
- All admin callbacks (`adm:*`) check `is_admin()` before any action. ✅
- User-scoped callbacks (`uwd:`, `uhist:`, `upart:`) derive the user from the callback author, not from payload. ✅ — no IDOR.
- Amounts, user IDs, withdrawal IDs in callbacks parsed strictly. ✅
- `callback_data` is attacker-influencable (Telegram allows crafting), but every handler re-validates and re-checks authorization. ✅
- **H1**: user-controlled text (first_name, username, withdrawal details, admin_comment) is interpolated into messages rendered with HTML parse mode without escaping → HTML injection and message-breaking.

## Authorization Audit

Matrix (server-side only):

| Operation | USER | ADMIN | Check location |
|---|---|---|---|
| /start, /profile, /referral, /partners, /balance, /collect, /top, /history, /withdraw, /my_withdrawals | ✅ | ✅ | from_user |
| /admin, /settings, /pending, /withdrawals, /stats, /approve, /reject, /confirm, /addcoins | ❌ | ✅ | `is_admin()` |
| adm:* callbacks | ❌ | ✅ | `is_admin()` before state mutation |
| uwd:/uhist:/upart: callbacks | ✅ own data | ✅ | from_user.id (scoped) |

Authorization always precedes state mutation. ✅

## Rate Limiting / Abuse

- `/collect`: atomic `consume_rate_limit` (3 attempts / 60s) + 24h cooldown inside txn. ✅
- Callbacks: atomic `consume_rate_limit` (10/60s user, 30/60s admin) in middleware. ✅
- `/start` and `/withdraw`: **non-atomic** `check_rate_limit` (SELECT count, then separate INSERT later). Under concurrency, a burst can pass the check before any row is inserted → limit bypass. Financial impact limited by downstream atomic guards, but the throttle is ineffective under load. (M1)
- `consume_rate_limit` returns `True` for users absent from `users` (FK failure swallowed) — non-registered users effectively bypass callback limiting (low impact; callbacks are read-only). INFO.
- Admin commands have no rate limit (admin-only surface). INFO.
- `user_actions` grows unboundedly; every callback, /start, /collect, /withdraw is recorded and never pruned → slow count queries over time. (M1)

## Error Handling Audit

- All DB mutation functions use try/except/ROLLBACK/finally-close; no partial mutations observed.
- `main.py` global error handler answers callbacks with a generic message and logs (traceback only at DEBUG → production loses stack traces; L7).
- Notification failures (`send_message`) are silently swallowed with `pass` — acceptable (best-effort), but hides problems from logs. INFO.
- Handler exceptions on malformed HTML are caught by the global handler, but the user just gets "Произошла ошибка" — combined with H1 this can be triggered remotely.

## Deployment Audit

- `requirements.txt`: `aiogram>=3.0,<4.0`, `python-dotenv>=1.0.0`. No upper pins on dotenv; no hashes. LOW (supply-chain).
- `Dockerfile`: python:3.11-slim, installs requirements, copies `referral_bot/`, `CMD python -m referral_bot.main`. Does **not** copy `.env` (correct). No disk mount in Docker — relies on Render for persistence.
- `render.yaml`: worker service, disk mounted at `/var/data` (1GB), `DB_PATH=/var/data/referral_bot.db`, BOT_TOKEN/ADMIN_IDS from secrets. Correct for SQLite persistence.
- Potential mismatch: dev DB at repo root has **no FKs** (see H2); deploying it to Render preserves the no-FK schema.

## Test Audit

Executed: 164/164 PASS.

- `test_database.py` (67): registration, referral, bonus accrual, daily reward, balance ops, withdrawal, approve/reject, levels, conditions, rate-limit, action log.
- `test_money_guard.py` (80): edge amounts, concurrent debit, parallel withdrawal, state machine, amount validation, referral guards, parallel confirm, parallel daily collect, parallel registration, ledger consistency, admin coin limits.
- `test_db_path.py` (17): DB_PATH env override/fallback, live DB read-only integrity.

Strengths: strong DB-layer concurrency + money-invariant coverage; tests use isolated temp DBs; ledger invariant asserted.

Gaps:
- No handler/middleware-layer tests (HTML escaping, is_admin gating, callback parsing, FSM flows).
- No test for H1 (malicious first_name / details breaking or injecting into messages).
- No test that legacy/no-FK DBs are migrated.
- No test for rate-limit bypass under concurrency for /start and /withdraw.
- No test for admin audit logging (M2).
- No test for settings boundary values (min_withdraw=0 etc.).

---

# Findings

## H1 — Unescaped user input rendered with HTML parse mode (CONFIRMED SECURITY ISSUE / BUG)
- Severity: **HIGH**
- File: `referral_bot/main.py:35` (global `parse_mode="HTML"`); consumers: `handlers/start.py:38-40,47`, `profile.py:24`, `referral.py:22-23,48-49`, `wallet.py:77`, `withdrawal.py:23-35,83`, `admin.py:78-81,141-143,169-172,220-223,258-263`, `callbacks.py:229,260-266,303-307,313-314`
- Description: first_name, username, withdrawal `details`, and `admin_comment` are user-controlled and interpolated into messages with f-strings; no `html.escape()` anywhere (grep confirmed).
- Impact: (a) HTML injection — a user can make their name render as `<a href=...>` in messages shown to **other users** (/top, /partners) and to **admins** (withdrawal details); (b) availability — a name containing unbalanced markup (e.g. `<b` or `<3`) makes Telegram return 400 for every message containing it, so `/top`, `/partners`, `/profile`, `/withdrawals` fail for everyone viewing.
- Reproduction: register a user with `first_name = "<a href=\"https://evil.example\">Click</a>"` → run `/top` as another user → rendered clickable link. Or first_name `"A<b"` → `/top` raises `TelegramBadRequest`.
- Root cause: user-controlled values injected into HTML-parsed message text without escaping.
- Recommended fix: add `utils/security.py` helper (`html.escape` / aiogram `html.quote`) and wrap every user-supplied value in message templates.
- Required regression test: handler-level or text-builder unit test with malicious first_name/details asserting escaped output and no exception.

## H2 — Live/deployed DB has no foreign keys; FK migration not wired (CONFIRMED DESIGN RISK)
- Severity: **HIGH** (integrity)
- File: `referral_bot/database/migrations.py:122-150` (`apply_foreign_key_migration`), `referral_bot/database/database.py:20-121` (`init_db`)
- Description: live `referral_bot.db` shows `PRAGMA foreign_key_list` empty for all tables. FK enforcement is enabled per-connection (`foreign_keys=ON`) but the constraints themselves are absent on legacy DBs. The provided migration that rebuilds transactions/withdrawals with FKs is deliberately not wired into `run_migrations`, and does not cover `referral_rewards`/`users`.
- Impact: orphan rows would be silently accepted by the DB if any future code path skips the app-layer guard; tests run on fresh FK-enabled DBs, so they can pass while production schema differs.
- Reproduction: inspect live DB `PRAGMA foreign_key_list(transactions)` → empty.
- Root cause: legacy schema never upgraded; migration left as manual ops step.
- Recommended fix: make FK rebuild part of a guarded, idempotent migration (verify zero orphans first), and extend it to all child tables; document/repeat on production.
- Required regression test: migration test that builds a legacy no-FK DB, runs migration, asserts `foreign_key_list` populated and `foreign_key_check` clean.

## M1 — Non-atomic rate limiting for /start and /withdraw; unbounded user_actions growth (CONFIRMED BUG)
- Severity: **MEDIUM**
- File: `referral_bot/handlers/start.py:19-21`, `referral_bot/handlers/withdrawal.py:47-49`, `referral_bot/database/database.py:606-658`
- Description: `check_rate_limit` (count-then-return) is separated from the later `log_user_action` INSERT; concurrent updates can all observe an empty window and pass the limit. Additionally `user_actions` is never pruned.
- Impact: throttle can be bypassed under concurrency; DB growth slows count queries over time.
- Reproduction: fire 50 concurrent `/start` for the same user within the window → more than 5 pass.
- Root cause: non-atomic check-then-act; no TTL cleanup.
- Recommended fix: use atomic `consume_rate_limit` for `/start` and `/withdraw` (as `/collect` already does); add periodic pruning or bucket tables.
- Required regression test: concurrency test asserting max-passed-actions <= limit.

## M2 — No audit log for sensitive admin financial actions (CONFIRMED GAP)
- Severity: **MEDIUM**
- File: `referral_bot/handlers/admin.py:148-263`, `referral_bot/handlers/callbacks.py:239-317`
- Description: `/approve`, `/reject`, `/confirm`, and their callback equivalents mutate balances/withdrawals but never call `log_user_action`. Only `/addcoins` is logged. `processed_by` exists on withdrawal rows but there is no operator action trail.
- Impact: cannot reconstruct "who approved/rejected/confirmed what, when" from the audit log; poor accountability for money movement.
- Recommended fix: log admin actions (`approve`, `reject`, `confirm`, with ids/amounts) via `log_user_action`.
- Required regression test: after approve/reject/confirm, `user_actions` contains the admin action.

## M3 — Settings allow unsafe boundary values (CONFIRMED DESIGN RISK)
- Severity: **LOW** (admin-only)
- File: `referral_bot/handlers/callbacks.py:414-421`
- Description: numeric settings use `parse_non_negative_int`, so `min_withdraw_amount`, `daily_reward_base`, `referral_bonus` can be set to 0 (min_withdraw=0 → any positive amount is withdrawable). Bounded by `MAX_SETTING_VALUE`.
- Impact: only an admin can trigger; still a foot-gun that silently changes financial behavior.
- Recommended fix: enforce per-key positive minimums (e.g., min_withdraw >= 1) in the settings processor.
- Required regression test: boundary test for each setting.

## M4 — No DB-level CHECK constraints (CONFIRMED DESIGN RISK)
- Severity: **LOW/MEDIUM** (defense-in-depth)
- File: `referral_bot/database/database.py:29-101`
- Description: no `CHECK(coins>=0)`, `CHECK(amount>0)`, `CHECK(status IN (...))`.
- Impact: integrity relies on the app layer only (compounded by missing FKs, H2).
- Recommended fix: add CHECK constraints via a guarded migration.
- Required regression test: attempt direct invalid INSERT/UPDATE → rejected.

## L1 — /help discloses admin commands to all users
- File: `referral_bot/handlers/help.py:22-27`. Low risk; consider hiding admin section for non-admins.

## L2 — `get_me()` called on every /referral
- File: `referral_bot/handlers/referral.py:14`. Unnecessary Telegram API call per request; cache bot username.

## L3 — `AutoRegisterMiddleware` performs a DB read that is never used
- File: `referral_bot/middlewares/__init__.py:14-24`. `data["db_user"]` is set but no handler reads it; remove or use.

## L4 — MemoryStorage FSM
- File: `referral_bot/main.py:36`. FSM (reject comment, settings edit) lost on restart/deploy; mid-flow sessions reset.

## L5 — Unbounded `details` / `admin_comment` length
- Files: `referral_bot/handlers/withdrawal.py:64`, `referral_bot/handlers/callbacks.py:296`. Bounded only by Telegram's 4096-char limit; enforce explicit caps for DB hygiene and admin views.

## L6 — Unused config constants
- `referral_bot/config.py:22` `REFERRAL_BONUS` never used (settings table is source of truth). Dead code / duplicate source of truth.

## L7 — Stack traces logged only at DEBUG
- File: `referral_bot/main.py:63`. Production (`INFO`) loses tracebacks, hurting diagnostics.

---

# Risk Matrix

| ID | Severity | Type | Area | Exploitable? |
|---|---|---|---|---|
| H1 | HIGH | Security / Bug | Messages | Yes (any user) |
| H2 | HIGH | Design risk | DB schema | Conditionally (future paths) |
| M1 | MEDIUM | Bug | Rate limit | Yes (concurrency) |
| M2 | MEDIUM | Gap | Audit | n/a |
| M3 | LOW | Design risk | Settings | Admin only |
| M4 | LOW/MED | Design risk | DB | Defense-in-depth |
| L1-L7 | LOW/INFO | Hardening | various | Minimal |

# Recommended Remediation Plan

Priority order:
1. **H1** — central HTML-escaping of user-controlled values (all handlers + a shared text-builder helper). Add regression test.
2. **H2** — wire and run a guarded FK migration; extend to all tables; add migration regression test.
3. **M1** — switch /start and /withdraw to atomic `consume_rate_limit`; add pruning; concurrency test.
4. **M2** — admin action audit logging; regression test.
5. **M4 + M3** — DB CHECK constraints; settings boundary validation.
6. **L1-L7** — hardening cleanups (help disclosure, get_me cache, middleware, FSM persistence, length caps, dead constants, traceback logging).

# Test Plan

- Execute `python -m referral_bot.tests.test_database`, `python -m referral_bot.tests.test_money_guard`, `python -m referral_bot.tests.test_db_path` (current baseline 164/164).
- Add per-fix regression tests listed under each finding.
- After all fixes: re-run full suite; add a handler-layer test module using aiogram's `MockTelegramBot`/`Dispatcher` for H1, M2, callback parsing.

# Final Assessment

The application is **structurally sound at the money layer**: transactions are atomic, idempotency is enforced, the ledger invariant holds, and the existing regression suite meaningfully covers concurrency and financial edge cases. The two highest-value changes are **escaping user-controlled text in HTML messages (H1)** and **migrating the live DB to enforce foreign keys (H2)**. No CRITICAL financial exploit was found; no production code was changed in this audit.
