# PROJECT STATE

## Current Git checkpoint

CR-03

Commit:
3cabc12

## Project

telegram-referral-bot

## Current objective

Prepare the project for a full technical audit and subsequent fixes.

## Completed

- Git repository initialized.
- Project committed to Git.
- Repository pushed to GitHub.
- .env excluded from Git.
- Database files excluded from Git.
- ackup_old_version/ excluded from Git.
- Initial checkpoint CR-03 created.

## Current status

The project is ready for a full audit.

No assumptions should be made about correctness.
All important functionality must be verified against the actual source code.

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
3. Run git status.
4. Run git diff.
5. Run git log --oneline -10.
6. Inspect the current uncommitted changes.
7. Determine the last completed task.
8. Continue from the first unfinished task.

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

## Current task

FULL AUDIT NOT STARTED YET.

## Next task

Perform a complete read-only audit of the repository before making modifications.

## Last update

2026-08-12
