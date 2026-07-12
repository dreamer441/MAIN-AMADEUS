---
description: Commit and push current AMADEUS work safely
---

Review the current Git changes and create a safe checkpoint.

Steps:
1. Run `git status`.
2. Run `git diff --stat`.
3. Inspect changed files enough to understand what changed.
4. Run `python -m compileall .`.
5. If compile succeeds, run `git add -A`.
6. Create a clear commit message using feat/fix/docs/refactor/chore.
7. Run `git commit -m "..."`
8. Run `git push`.
9. Report the commit hash and short summary.

Safety:
- Do not force-push.
- Do not reset, restore, or clean files.
- Do not commit secrets, API keys, .env files, model files, or cache folders.
- If compile fails, stop and explain the issue instead of committing.
