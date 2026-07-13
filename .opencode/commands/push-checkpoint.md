---
description: Commit and push current AMADEUS work safely
---

Review the current Git changes and create a safe checkpoint.

Steps:
1. Run `git status`.
2. Run `git diff --stat`.
3. Inspect changed files enough to understand what changed.
4. Run `python -m compileall .`.
5. Confirm `AMADEUS_CHANGELOG.md` contains the completed-task entry with Date, Phase, Feature or fix, What changed, Files/modules affected, User-visible behavior, Architecture notes, Tests performed, and Known limitations.
6. If validation succeeds, stage only the reviewed intended files. Do not use `git add -A`.
7. Run `git diff --cached --stat` and inspect the staged paths.
8. Create a clear commit message using feat/fix/docs/refactor/chore.
9. Run `git commit -m "..."`
10. Run `git push`.
11. Report the commit hash, concise file-change summary, validation result, and push result.

Safety:
- Do not force-push.
- Do not reset, restore, or clean files.
- Do not commit secrets, API keys, .env files, model files, or cache folders.
- Do not commit runtime data under `data/chats/`, `data/comments/`, `data/memory/`, `data/sheets/`, or `data/exports/`.
- If compile fails, stop and explain the issue instead of committing.
