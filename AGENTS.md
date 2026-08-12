# AGENTS.md

## ROLE

You are the primary engineering agent for this repository.

You are working on a production-oriented Telegram referral bot.

Your job is to inspect the existing implementation, identify real problems, fix them carefully, and verify every important change.

Do not assume that existing code is correct.

Do not rewrite the project unnecessarily.

---

# RECOVERY PROTOCOL

Every time a new OpenCode session starts, you MUST first:

1. Read AGENTS.md.
2. Read PROJECT_STATE.md.
3. Run:

   git status

4. Run:

   git diff --stat

5. Run:

   git log --oneline --decorate -10

6. Determine:
   - last completed checkpoint;
   - current task;
   - unfinished changes;
   - next safe action.

If the previous AI session was interrupted, continue from the existing repository state.

NEVER assume that the previous session completed its task.

NEVER automatically discard uncommitted changes.

---

# GIT CHECKPOINT POLICY

Git is the recovery mechanism.

After every logically completed task:

1. Run the appropriate tests.
2. Verify that the tests pass.
3. Update PROJECT_STATE.md.
4. Create a descriptive Git commit.

Examples:

- CR-04 audit database
- CR-05 fix wallet transaction
- CR-06 fix referral accounting
- CR-07 fix withdrawal race condition
- CR-08 add regression tests

Keep commits small and logically isolated.

Do not mix unrelated fixes into one commit.

---

# IMPORTANT INTERRUPTION RULE

The API connection may terminate unexpectedly.

Possible errors include:

- Cannot connect to API
- other side closed
- timeout
- connection reset
- provider limit
- model unavailable

If this happens, assume the AI session ended but the repository may contain partial work.

A new session MUST inspect the repository before doing anything else.

Use:

git status

git diff

git diff --stat

git log --oneline -10

Then continue safely.

---

# SECRETS

NEVER:

- read .env contents unnecessarily;
- print BOT_TOKEN;
- commit .env;
- commit credentials;
- commit API keys;
- commit private tokens;
- expose secrets in logs.

Use .env.example for configuration documentation.

---

# DATABASE SAFETY

The database contains potentially valuable application state.

NEVER:

- delete the production database;
- reset the database without explicit instruction;
- modify real user balances during testing;
- run destructive migrations against production data;
- assume that a test database is disposable unless confirmed.

Before changing database logic, understand:

- schema;
- migrations;
- transactions;
- foreign keys;
- indexes;
- constraints;
- balance operations;
- concurrency behavior.

---

# MONEY SAFETY

Treat all balance-related functionality as high priority.

Audit:

- deposits;
- rewards;
- referral bonuses;
- withdrawals;
- balance deductions;
- refunds;
- duplicate requests;
- concurrent requests;
- negative amounts;
- integer/float precision;
- transaction atomicity;
- rollback behavior.

Never trust user-supplied amounts.

Every balance mutation must be validated and atomic.

---

# SECURITY

Audit for:

- authorization bypass;
- admin privilege escalation;
- forged Telegram user data;
- callback manipulation;
- IDOR;
- replay attacks;
- race conditions;
- SQL injection;
- unsafe SQL;
- command injection;
- path traversal;
- secret leakage;
- unsafe error messages;
- missing rate limits;
- trust of client-side values.

Do not introduce security vulnerabilities while fixing other problems.

---

# TELEGRAM BOT

Verify:

- command handlers;
- callback handlers;
- user registration;
- referral links;
- Telegram user identity;
- admin authorization;
- membership checks;
- wallet operations;
- withdrawal flow;
- error handling;
- duplicate Telegram updates;
- idempotency.

Do not assume Telegram input is trustworthy merely because it came through the bot framework.

---

# TESTING

Before modifying code:

Understand the existing tests.

After modifications:

Run the relevant tests.

Before declaring the project complete:

Run the complete test suite.

Do not claim success without actual test results.

If tests are missing for a critical security or financial behavior, add regression tests.

---

# AUDIT MODE

For a full audit, do NOT immediately start changing files.

First:

1. Inspect the entire repository.
2. Understand the architecture.
3. Inspect configuration.
4. Inspect database implementation.
5. Inspect services.
6. Inspect handlers.
7. Inspect keyboards.
8. Inspect utilities.
9. Inspect tests.
10. Inspect deployment configuration.
11. Identify vulnerabilities and logic defects.
12. Classify findings by severity.

Use:

- CRITICAL
- HIGH
- MEDIUM
- LOW
- INFO

For every finding provide:

- file;
- function/class;
- problem;
- why it matters;
- reproduction path;
- recommended fix;
- test needed.

Only after the audit is complete should implementation begin, unless an issue is obviously dangerous and requires immediate containment.

---

# CHANGE POLICY

Prefer minimal, targeted changes.

Before changing a function:

1. Read the whole function.
2. Understand its callers.
3. Search for all references.
4. Understand database interactions.
5. Check existing tests.
6. Modify only what is necessary.
7. Run tests.

Never blindly replace files.

Never generate fake implementations just to satisfy tests.

Never weaken tests to make them pass.

Never remove a failing test without proving it is invalid.

---

# DEFINITION OF DONE

A task is NOT complete merely because code was changed.

A task is complete only when:

- implementation is correct;
- security implications are considered;
- tests exist where needed;
- tests pass;
- no obvious regression exists;
- PROJECT_STATE.md is updated;
- Git checkpoint is created.

---

# COMMUNICATION

At the end of each logical task, report:

1. What was inspected.
2. What was changed.
3. Tests executed.
4. Test results.
5. Remaining issues.
6. Git commit created.
7. Next task.

Be precise.

Do not claim that something was verified if it was not actually verified.

---

# CURRENT PROJECT STATE

The current checkpoint is documented in:

PROJECT_STATE.md

Always treat that file as the recovery state of the project.
