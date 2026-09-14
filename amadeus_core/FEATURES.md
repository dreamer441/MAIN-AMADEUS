# AMADEUS Core - Current Features

## Responsibility

Core exposes explicit routes to registered owners. Startup construction belongs to
`amadeus_app`; feature modules execute requests. Importing Core does not load
feature implementations or Qt. Tests can inject a registry.

## Public routes preserved

- Dedicated-chat messages, annotations, annotation blocks, callable context and
  response modes route to Chat Workspace. Context Builder selects context,
  Annotation interprets syntax, Chat generates, and Storage persists records.
- Flow requests and history route to Flow's request handler, retaining separate
  history, metadata-only chat discovery and deterministic Habit commands.
- Chat creation, selection, deletion and metadata updates route to Chat Workspace
  lifecycle; metadata refresh and exports route to its metadata service.
- Sheet/comment actions and linked panels route to Workspace Documents.
- Materials list, preview, open, reference-copy, removal and explicit questions
  route to Materials Workspace. Selection alone does not inject context.
- Code Viewer tree/file reads and explicit file questions route to Project File
  Workspace. Exact access remains verified by Project File Reader.
- Side Ask routes to its workflow; temporary questions persist only on explicit save.
- Mind Map CRUD, source edits/deletion, search, subscriptions and import/export
  route to Graph Workspace and the Mind Map owner. Workspace Integration owns
  cross-module synchronization and the locked Canvas projection.
- `core.canvas` explicitly routes Canvas document, block, connector and workspace
  operations. Canvas request handling and generation stay in Canvas.
- `core.habits` explicitly routes to the same Habit service used by Flow; the GUI
  receives this facade instead of constructing a second application service.
- Creation proposals route to Creation. Pending-action creation, approval and
  decline route to PermissionGuard, which dispatches registered owner callbacks.
- Annotation suggestions route to Annotation; completion/response presentation
  belongs to Response Modes. Response dictionaries and event delivery remain compatible.

## Compatibility

`AmadeusCore` remains available from `amadeus_core.core`. Existing service
accessors remain for callers migrating to routes. Historical pending-action and
creation-workspace-adapter imports re-export their new owners. Core does not
contain duplicate feature implementations or arbitrary method-name dispatch.

## Ownership cleanup completed 2026-09-14

See `docs/ARCHITECTURE.md` for the complete owner map and
`docs/CORE_CLEANUP_REPORT.md` for changes, validation and manual checks.
