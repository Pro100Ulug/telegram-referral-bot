# PROJECT STATE

## Current Git checkpoint

CR-06

Commit:
ec74da6

## Project

telegram-referral-bot

## Current objective

Complete read-only audit of the repository and prepare for controlled fixes.

## Completed

- Git repository initialized.
- Project committed to Git.
- Repository pushed to GitHub.
- .env excluded from Git.
- Database files excluded from Git.
- backup_old_version/ excluded from Git.
- Initial checkpoint CR-03 created.
- CR-04 added project recovery state.
- CR-05 added OpenCode recovery protocol.
- CR-06 full read-only audit completed.
- AUDIT_REPORT.md produced.
- Full test suite executed: test_database 67/67, test_money_guard 80/80, test_db_path 17/17 (164/164 PASS).

## Current status

The full read-only audit is COMPLETE. No production code was modified during the audit.

Findings classified:
- CRITICAL: none
- HIGH: H1 (HTML injection in messages), H2 (live DB lacks foreign keys, FK migration not wired)
- MEDIUM: M1 (non-atomic rate limit /start & /withdraw), M2 (no admin audit log)
- LOW: M3 (settings allow 0 boundaries), M4 (no DB CHECK constraints), L1-L7 hardening items

See AUDIT_REPORT.md for the complete findings list, risk matrix, and remediation plan.

## Current task

AWAITING USER AUTHORIZATION to start fixes.

## Next task

Fix in priority order once authorized:
1. H1 — HTML escaping of user-controlled values
2. H2 — wire+run guarded FK migration (extend to all child tables)
3. M1 — atomic rate limiting for /start and /withdraw
4. M2 — admin action audit logging
5. M4 + M3 — DB CHECK constraints + settings bounds
6. L1-L7 — hardening cleanups

## Audit areas

1. Project architecture
2. Configuration and environment variables
3. Database schema and migrations
4. Database transactions
5. User balance / money operations
6. Referral system
7. Wallet functionality
8. Withdrawal system
9. Telegram handlers
10. Callback handling
11. Admin functionality
12. Security
13. Authentication / authorization
14. Race conditions
15. Error handling
16. Logging
17. Docker / deployment
18. Render configuration
19. Tests
20. Regression risks

## Recovery rules

If an OpenCode session is interrupted:

1. Do not start the project from scratch.
2. Read this file first.
3. Read AUDIT_REPORT.md.
4. Run git status.
5. Run git diff.
6. Run git log --oneline -10.
7. Inspect the current uncommitted changes.
8. Determine the last completed task.
9. Continue from the first unfinished task.

Never discard uncommitted changes automatically.

## Git checkpoint rules

After every logically completed task:

1. Run relevant tests.
2. Verify the result.
3. Update this file.
4. Create a Git commit.

Do not keep a large number of unrelated changes uncommitted.

## Safety rules

- Never read, print, or commit .env.
- Never expose BOT_TOKEN.
- Never commit database files.
- Never delete functionality without evidence.
- Never rewrite large parts of the project without first understanding the existing architecture.
- Preserve working functionality.
- Prefer small, testable changes.
- Run regression tests after fixes.

## Known issues (high priority)

- H1: user-controlled text rendered with parse_mode="HTML" without escaping — HTML injection + message-breaking.
- H2: live/production DB has no foreign keys; apply_foreign_key_migration not wired into run_migrations.
- M1: check_rate_limit is non-atomic for /start & /withdraw; user_actions grows unboundedly.
- M2: no audit trail for admin approve/reject/confirm actions.

## Last update

2026-08-12