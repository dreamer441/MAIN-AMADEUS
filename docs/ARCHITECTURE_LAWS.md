# AMADEUS V2 Architecture Laws

These laws protect AMADEUS V2 from becoming messy as features are added.

1. Core routes, modules execute.
2. Core stays lightweight.
3. Core never imports module internals.
4. Modules expose public APIs.
5. Submodules belong to modules.
6. Risky actions require PermissionGuard.
7. Storage stores, Context Builder selects, LLM Client answers.
8. No silent system actions.

## Layer Rule

AMADEUS has three layers:

1. Core
2. Modules
3. Submodules

Core coordinates. Modules provide feature systems. Submodules are private implementation pieces owned by modules.
