# AMADEUS OpenCode Rules

## Project identity

This repository is AMADEUS, a local-first personal AI companion project.
AMADEUS should remain modular, stable, readable, and expandable.

Core rule:
- Core routes.
- Modules execute.
- Submodules extend modules.
- Skills provide abilities.
- Storage stores.
- PermissionGuard protects.

## Coding rules

- Keep modules independent.
- Do not create hidden dependencies between modules.
- Add clear comments explaining what each file/class/function is responsible for.
- Prefer simple, readable code over clever code.
- Update FEATURES.md and FUTURE_UPDATES.md when adding or changing module behavior.
- Do not remove existing features unless explicitly instructed.

## Git workflow rules

At the start of every task:
1. Run `git status`.
2. Notice the current branch.
3. Avoid touching unrelated files unless required by the task.

After every completed implementation task:
1. Run a basic Python check:
   `python -m compileall .`
2. If tests exist, run the relevant tests.
3. Run:
   `git status`
   `git diff --stat`
4. Stage intended changes:
   `git add -A`
5. Create a local commit with a clear message:
   `git commit -m "type: short summary"`
6. Push the current branch:
   `git push`

Commit message style:
- `feat:` for new features.
- `fix:` for bug fixes.
- `docs:` for documentation only.
- `refactor:` for restructuring.
- `chore:` for maintenance/checkpoints.

## Auto-push rule

The user wants automatic pushing by default.
After completing a task successfully, commit and push without asking again.

## Safety rules

Never run these commands unless the user explicitly asks:
- `git reset --hard`
- `git clean -fd`
- `git restore .`
- `git push --force`
- `git push --force-with-lease`

Never commit or push:
- `.env`
- API keys
- secrets
- passwords
- private tokens
- model files
- cache folders
- temporary generated junk

If `python -m compileall .` fails, do not commit or push. Explain the error first.
