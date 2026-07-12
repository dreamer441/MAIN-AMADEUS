# AMADEUS Module Rules

1. Every major system gets its own folder.
2. Every module folder must include `README.md`, `FEATURES.md`, and `FUTURE_UPDATES.md`.
3. Modules should not directly control unrelated modules.
4. Core coordinates communication between modules.
5. GUI calls Core, not feature modules directly.
6. Core routes, modules execute.
7. Placeholder modules should stay simple until their real purpose is implemented.
8. File reading must stay read-only unless a future permission system explicitly allows more.
9. Annotation parsing belongs in the Annotation Module, not in Chat.
10. Context selection belongs in Context Builder, not directly inside Chat or GUI.
11. Identity is global; reasoning profiles are temporary and must not erase identity.
12. Trace / Process Monitor must record real execution events only. It must not invent hidden thinking.
13. Every feature change must update the affected module `FEATURES.md` and `FUTURE_UPDATES.md` files.
14. Code comments are required for readability. Comments should explain architecture, ownership, data flow, and safety boundaries.
15. Small stable patches are preferred over large rewrites.

See `docs/DEVELOPMENT_WORKFLOW_RULES.md` for the detailed documentation and code-comment workflow.
16. Memory V1 is explicit only: AMADEUS saves durable memory only when Dato uses `[memory]`.
17. Memory lists belong in the right panel by default so main chat stays clean.
