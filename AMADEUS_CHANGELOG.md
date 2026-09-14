# AMADEUS Global Changelog

Append-only global project progress log. Module-specific details still belong in each module's `FEATURES.md` and `FUTURE_UPDATES.md`.

## 2026-09-15 - Behavior Preserving Code Polish

- Date: 2026-09-15 (implementation began 2026-09-14).
- Phase: Maintenance after the Core ownership cleanup.
- Feature or fix: Separate large presentation files and remove local duplication without adding features.
- What changed: Moved Canvas dialogs/editors, graphics items, surface and shared geometry constants into focused files within `canvas_module/gui`. Moved Mind Map dialogs and surface into focused files within `mindmap/gui`; consolidated duplicate spin-box construction behind the existing instance methods. Simplified Canvas context-role priority assignment into one ordered loop. Preserved original view imports for extracted components.
- Files/modules affected: Canvas GUI `view.py`, `dialogs.py`, `items.py`, `surface.py`, `constants.py`, Canvas `context.py`; Mind Map GUI `view.py`, `dialogs.py`, `surface.py`; both module READMEs, FEATURES and FUTURE_UPDATES; `docs/superpowers/plans/2026-09-14-code-polish.md` and this changelog.
- User-visible behavior: Existing editing, drawing, selection, dialogs, context ordering, prompts, token budgets, approvals and data formats are preserved. Canvas view reduced from 2,235 to 1,261 lines; Mind Map view from 1,578 to 1,285 lines. Most code is relocated, not deleted.
- Architecture notes: Presentation helpers remain inside their owning modules and never import their coordinating views. Core/service interfaces and storage ownership are unchanged. Equal class bodies were checked structurally against the prior commit; the only deliberate method-body changes are the documented helper delegation and context-loop simplification.
- Tests performed: Canvas and workspace boundary tests passed (69); Mind Map and annotation tests passed (32). All 600 generated old/new Canvas context packages matched exactly. Python compileall passed. The full regression suite passed all 336 tests in 81.759 seconds. Final review results are recorded in the completed plan.
- Known limitations: This is maintainability polish, not a measured speed improvement. Extracted classes now identify their defining helper module in Python introspection; historical class imports from the view still resolve to those same classes. Runtime monkeypatches of a helper's globals must target its defining module. Live interactive GUI checks were not performed. Push remains subject to the previously blocked remote-destination approval.

## 2026-09-14 - Core Ownership Cleanup

- Date: 2026-09-14 (approved design and extraction began 2026-09-12).
- Phase: Modular architecture cleanup.
- Feature or fix: Restore Core routing boundaries while retaining the existing feature set.
- What changed: Extracted startup composition into `amadeus_app`, dedicated conversation workflows into `chat_workspace`, and cross-owner graph/source workflows into `workspace_integration`. Flow, Canvas, Creation, Habit Tracker, Materials, Project File Reader, Side Ask, Context Builder and Response Modes now own their former Core execution helpers. PermissionGuard owns single-use approval dispatch. Added explicit Canvas/Habit Core facades, shared Habit GUI injection, plain Sheet target resolution and compatibility re-exports. Updated ownership documentation and ignored all local runtime stores.
- Files/modules affected: Core and the owner packages above; Annotation, GUI, Sheets, Mind Map compatibility integration, regression fixtures, module FEATURES/FUTURE_UPDATES and READMEs, architecture rules, `.gitignore`, approved design/plan and `docs/CORE_CLEANUP_REPORT.md`. The report contains the exact incremental file inventory.
- User-visible behavior: Existing chat, Flow, annotations, selected-context requests, approvals, Canvas, Mind Map, Habit and persistence workflows remain available. Core's implementation no longer owns their feature behavior. No data reset or feature removal is part of the cleanup.
- Architecture notes: Core routes through explicit registered interfaces; application setup injects dependencies. Modules execute through public owner APIs; storage stays with its owner. PermissionGuard protects existing proposals and is not a system sandbox. Historical imports remain lightweight compatibility exports. Existing uncommitted feature source required by the composed application is preserved in the delivery.
- Tests performed: Full Python compilation passed; all 336 tests passed together and across 25 isolated module runs. Independent ownership and delivery reviews passed. Commands are recorded in `docs/CORE_CLEANUP_REPORT.md`. Updated stale fixture contracts and drained pending Qt refresh workers before test window disposal.
- Known limitations: Live Ollama quality and interactive desktop/restart checks are provided as a manual checklist. Compatibility accessors and broad service types remain; general skill permissions, a skill runner, reasoning implementation and cross-owner transaction compensation are future work.

## 2026-08-05 - Flow Habit Request Boundary Redesign

- Date: 2026-08-05
- Phase: Flow-to-Habit Tracker integration
- Feature or fix: Replaced the direct fragile Flow Habit parser route with a typed request boundary.
- What changed: Raw Flow Habit text now passes through a dedicated boundary that normalizes bounded task phrases, uses Creation task preparation through the existing interpreter, returns deterministic reads or validated approval requests, and converts all parser validation failures into user-safe responses.
- Files/modules affected: `flow_chat` Habit request service, Core Flow coordination, focused Flow Habit tests, Flow/Core module documentation, and this changelog.
- User-visible behavior: Natural and slash task forms, including dated tasks and urgent/important matrix tasks, request approval and persist only after approval. Invalid dates, times, titles, and unsupported Habit commands return specific local guidance instead of a generic Flow failure.
- Architecture notes: Habit Tracker remains the only persistence owner. Core registers only the boundary's validated typed approval fields and dispatches them after the existing pending-action approval.
- Tests performed: Focused Flow Habit tests and Python compilation are recorded in the task report.
- Known limitations: Natural language remains deliberately bounded to the deterministic Habit grammar; no LLM-derived dates, identifiers, or write fields are accepted.

## 2026-08-05 - Flow Habit Task Creation Fix

- Date: 2026-08-05
- Phase: Flow-to-Habit Tracker integration
- Feature or fix: Fixed natural one-time and Eisenhower task creation routing.
- What changed: Flow now defaults an undated one-time task to today, extracts supported natural dates before optional field clauses, and removes the `Eisenhower task` label from the stored task title.
- Files/modules affected: `flow_chat` parser, Core/GUI approval-path regression tests, module documentation, and the Flow task creation report.
- User-visible behavior: `create a task Buy groceries`, `add a task Buy groceries tomorrow`, and Eisenhower task requests return a visible Habit Tracker approval instead of failing, falling through to the LLM, or returning read-only guidance.
- Architecture notes: Flow remains deterministic; Core registers and consumes the integrity-checked `habit_tracker` pending action; the GUI only displays and approves its payload.
- Tests performed: `tests.test_flow_habit_commands` and the focused Flow GUI Habit Tracker approval-payload test passed; `py -3.13 -m compileall .` passed. The broader Flow GUI module retains an unrelated Canvas storage-facade test failure.
- Known limitations: Natural dates remain intentionally bounded to today, tomorrow, next weekday, and ISO dates; urgency and importance remain explicit `urgent:` and `important:` fields.

## 2026-08-05 - Flow Habit Tracker Parity

- Date: 2026-08-05
- Phase: Flow-to-Habit Tracker integration
- Feature or fix: Added approval-gated deterministic Flow control for Habit Tracker.
- What changed: Added `/habit` reads and bounded natural aliases for routines, one-time tasks, calendar events, Eisenhower tasks, timers, and alarms. Added matrix update/completion/scheduling and explicit alarm owner APIs with additive SQLite migration. Task content is validated by Creation before Core prepares a pending owner action.
- Files/modules affected: `flow_chat`, `habit_tracker`, `creation_module`, `amadeus_core`, focused tests, module documentation, and this changelog.
- User-visible behavior: Flow can list Habit Tracker state and request every supported action. Writes and destructive actions show the existing approval UI; ambiguous dates/times and empty tasks are rejected locally with guidance.
- Architecture notes: Flow parses only deterministic grammar, Creation prepares task content, Core coordinates pending actions, and Habit Tracker remains the only SQLite owner.
- Tests performed: `py -3.13 -m compileall .`; focused Flow/Habit Tracker/Core approval tests.
- Known limitations: The existing Habit Tracker GUI has not yet added controls for matrix editing/completion or explicit alarms; Flow exposes those owner capabilities now.

## 2026-08-05 - Mind Map Canvas Projection

- Date: 2026-08-05
- Phase: Canvas/Mind Map workspace synchronization
- Feature or fix: Added the read-only Mind Map Canvas projection alongside automatic source-backed Canvas projection to Mind Map.
- What changed: Persisted Canvas block and connector mutation events project stable `canvas_block` nodes and `canvas_connector` links into Mind Map. Eligible Mind Map source nodes (`chat`, `sheet`, `memory`, `comment`, and `canvas_block`) and links with two eligible endpoints now reconcile into the dedicated `mindmap_projection` Canvas workspace titled `Mind Map`. Canvas-backed Mind Map nodes render as compact `84 x 40` rounded rectangles, and Canvas connector relation type, label, and comment map to link type, label, and evidence.
- Files/modules affected: `canvas_module`, `mindmap` workspace synchronization and GUI items, `amadeus_core` coordination, focused Canvas/Mind Map tests, module documentation, and this changelog.
- User-visible behavior: Canvas blocks and connectors appear in Mind Map automatically. Eligible Mind Map source records and their mutual links also appear in the separate locked `Mind Map` Canvas workspace. Deleting either Canvas source removes its graph projection; deleting a projected Mind Map node or link removes its Canvas source. Chat-backed nodes remain elliptical.
- Architecture notes: Canvas owns block and connector content, layout, and semantics. Core subscribes the synchronization bridge after composing the Canvas facade; the bridge uses stable source references and Canvas events to avoid deletion loops. The reverse projection is managed only by reconciliation: metadata marks its locked Canvas records and prevents them from re-entering the Canvas-to-Mind Map bridge. Manual Mind Map creation and source-content edits never create or edit Canvas blocks.
- Tests performed: `py -3.13 -m compileall .`; `py -3.13 -m unittest tests.test_canvas_module tests.test_mindmap_workspace_sync tests.test_mindmap -v`.
- Known limitations: Only eligible source-backed Mind Map nodes and links with two eligible endpoints appear in the read-only `Mind Map` Canvas workspace. Managed projection records cannot be edited or deleted from Canvas; source changes must occur in the owning Mind Map or workspace module.

## 2026-08-04 - Phase: Module Metadata Annotation

- Feature or fix: Read-only module metadata annotation and general-chat inference.
- What changed: Added verified aggregation of FEATURES.md and FUTURE_UPDATES.md, guided [metadata] suggestions, Memory-panel display, and bounded general-chat open/answer routing.
- Files/modules affected: project_file_reader, annotation_module, inner_brain, amadeus_core, amadeus_gui, and focused tests.
- User-visible behavior: Dato can browse module metadata with guided annotations or ask general chat to show/explain it; Flow Chat does not infer it.
- Architecture notes: ProjectFileReader owns fixed-file reads; annotations render results; Core validates routing; Inner Brain remains advisory.
- Tests performed: Focused reader, annotation, GUI, Inner Brain, Core, Flow tests; py -3.13 -m compileall .
- Known limitations: Aggregate metadata output is bounded and does not edit or persist module documents.

## 2026-08-02 - Chat Action Approval

- Date: 2026-08-02
- Phase: Core-owned action approval
- Feature or fix: Replaced optimistic inferred and explicit Flow creation with visible approval requests.
- What changed: Added a bounded, TTL-limited, integrity-hashed, single-use Core pending-action registry. Normal-chat write candidates and `/create-chat`, `/create-sheet`, `/create-comment`, and `/create-memory` now return `approval_request`; Flow and dedicated Chats show the shared Approve / Decline dialog and only approve through Core's existing owner facades.
- Files/modules affected: Core pending-action service and coordinator, Flow Chat, Inner Brain integration, shared GUI dialog and response handlers, focused tests, module documentation, and this changelog.
- User-visible behavior: AMADEUS no longer reports a requested creation as completed before it occurs. Decline writes nothing; approval performs the existing owner action and its Mind Map synchronization.
- Architecture notes: Only chat, sheet, comment, memory, and export actions are registered. Pending state is process-local and does not permit arbitrary filesystem, shell, or external operations.
- Tests performed: Pending lifecycle, Inner Brain, Flow, and mocked headless GUI approval tests; full compile and whitespace validation are run with this change.
- Known limitations: Pending requests expire after five minutes and are lost on application restart; approval dialogs are modal by design.

## 2026-08-02 - Inner Brain Flow Inference Safety

- Date: 2026-08-02
- Phase: Local advisory Flow analysis
- Feature or fix: Closed the Inner Brain V1 Flow inference gap without enabling inferred actions.
- What changed: Core now injects a narrow callback into Flow that analyzes plain messages with `route="flow"` and returns only bounded context from the existing no-argument read annotation handler. Explicit `/review`, `/create-chat`, `/create-sheet`, `/create-comment`, and `/create-memory` commands skip inference.
- Files/modules affected: Core coordinator, Flow Chat service, Inner Brain and Flow documentation, focused Flow tests, and this changelog.
- User-visible behavior: Plain Flow requests can receive safe inferred project read context. Flow commands keep their established explicit behavior. Advisory write candidates do not create or modify anything.
- Architecture notes: Flow imports no Core or annotation internals. Core retains Inner Brain invocation and annotation ownership; Flow accepts only a text-context callback result.
- Tests performed: Focused fake-Inner-Brain Flow tests plus Python compilation.
- Known limitations: Inference is limited to existing no-argument `file`, `sheet`, `export`, and `mindmap` read handlers and does not accept model-provided locators or execute writes.

## 2026-08-02 - Inner Brain V1

- Date: 2026-08-02
- Phase: Local advisory chat analysis
- Feature or fix: Added a separate strict-JSON Nemotron Inner Brain for safe dedicated-chat advisory analysis and explicit five-layer chat metadata.
- What changed: Added a pure injected `inner_brain` service using `nemotron-3-nano:4b`, additive chat-index metadata migration, explicit Analyze / Refresh and Create Export Core actions, Chat Data side-panel rendering, and Mind Map source-node metadata projection. Plain dedicated-chat inference uses only no-argument existing read handlers; inferred write candidates are display-only.
- Files/modules affected: `inner_brain`, Storage, Core coordinator, dedicated-chat side panel, Mind Map workspace synchronization, focused tests, and module documentation.
- User-visible behavior: Chat Data displays title, description, short summary, detailed summary, export reference, model status, and non-executable suggested writes. Refresh is explicit; exports are created only from the explicit control.
- Architecture notes: The primary LLM is unchanged. Inner Brain has no persistence, export, filesystem, or graph access. Storage owns the index record and Core owns routing, export calls, and graph resynchronization.
- Tests performed: Focused fake-Inner-Brain/service, storage migration, annotation Core, Mind Map synchronization, and headless GUI tests; Python compilation and Git whitespace validation.
- Known limitations: Flow annotation inference is not integrated in this increment. Its explicit Flow commands remain authoritative, and metadata refresh stays explicit.

## 2026-08-02 - Immediate Flow Creation And Annotations

- Date: 2026-08-02
- Phase: Controlled Creation workspace handoff
- Feature or fix: Replaced Flow workspace proposal approval with immediate scoped creation and added Flow annotation suggestions.
- What changed: `/create-sheet`, `/create-comment`, and `/create-memory` now validate then call one Core-owned workspace adapter immediately. Their default scope is global and unlinked; only the exact final `; scope: chat` suffix links to the active dedicated chat. Comments now persist explicit `global` or `chat` scope with optional owner migration for legacy chat records. Flow composes the existing annotation suggestion backend with Flow-only staged `/create` commands.
- Files/modules affected: `creation_module`, `flow_chat`, `comments_module`, Core composition, Mind Map workspace sync, Flow GUI, focused tests, module documentation, and this changelog.
- User-visible behavior: Flow creation commands create records immediately. Global records do not appear in dedicated-chat linked context; explicitly chat-scoped Sheet, Comment, and Memory records do. In Flow, `/` opens the annotation popup, `/create` advances to creation commands, arrows navigate, Enter/Tab insert, Escape hides, and normal Enter sends when hidden. Dedicated Chat does not expose Flow commands.
- Architecture notes: Creation remains orchestration-only and never writes owner stores or Mind Map directly. Core composes the adapter, owner modules persist, and Core then synchronizes the graph. Existing chat comments and `[memory]` behavior remain unchanged.
- Tests performed: Focused comments, Creation, Flow, Mind Map synchronization, and headless annotation/Flow GUI tests; full Python compilation and Git whitespace validation.
- Known limitations: `/approve` is no longer a Flow action and is treated as normal Flow text. Global comments have no dedicated global-panel UI yet. The existing Canvas fake-Core GUI test remains unrelated to this feature.

## 2026-08-02 - Flow Workspace Creation Commands

- Date: 2026-08-02
- Phase: Controlled Creation workspace handoff
- Feature or fix: Added explicit Flow Sheet, Comment, and Memory proposal and approval commands.
- What changed: Added `/create-sheet`, `/create-comment`, and `/create-memory` temporary Flow-session proposals plus `/approve <id[, id...]>`. Creation validates typed proposals and calls a Core-composed owner adapter only after explicit selection. The adapter uses the existing Sheet, Comment, and Memory public services, then calls existing Mind Map workspace synchronization methods.
- Files/modules affected: `creation_module`, `flow_chat`, Core coordinator composition, focused Creation/Flow/Mind Map tests, module documentation, and this changelog.
- User-visible behavior: Creation commands return a proposal ID and do not persist anything until `/approve`. Approved chat-scoped Sheets, Comments, and Memories are linked to the active dedicated chat and appear as literal direct-neighbor context in later dedicated-chat prompts. Memory supports chat scope by default and `; scope: global`.
- Architecture notes: Flow owns only in-memory proposal session state. Creation performs no JSON, SQLite, GUI, Canvas, or Mind Map writes. Core composes the adapter; existing owner services remain persistence authorities and Mind Map sync occurs only after owner persistence. Existing `[memory]` behavior is unchanged.
- Tests performed: Focused Creation approval validation, Flow command lifecycle, owner-service/Mind Map synchronization, and captured fake-LLM linked-context regression; Python compilation and Git whitespace validation.
- Known limitations: Commands use simple request text with strict JSON generation only for missing Sheet title metadata and safe fallbacks if generation is unavailable. There is no proposal review GUI, natural-language intent routing, or Second Brain routing.

## 2026-08-02 - Flow Create Chat Command

- Date: 2026-08-02
- Phase: Flow Chat dedicated-workspace creation
- Feature or fix: Added explicit `/create-chat <request>` dedicated chat creation.
- What changed: Added Flow-owned command parsing, recognized Title/Description/Weight/Priority metadata fields, strict Ollama JSON metadata generation for missing fields, safe defaults for unavailable or invalid JSON, and a typed created-chat response payload. Core injects its existing `create_chat()` facade so storage persistence and Mind Map source-node synchronization remain unchanged. The GUI validates the payload, refreshes the selector, and opens the created workspace on its Qt GUI thread.
- Files/modules affected: `flow_chat`, Core coordinator composition, Flow GUI shell, focused Flow/Mind Map/GUI tests, Flow documentation, future implementation tracking, and this changelog.
- User-visible behavior: `/create-chat <request>` creates an editable dedicated chat and opens it automatically. Explicit metadata wins; missing metadata is generated locally when possible or defaults to New Chat, empty description, and Normal priority. Normal Flow and `/review` remain unchanged.
- Architecture notes: Flow owns command parsing and metadata resolution. Core remains the sole route to `create_chat()` and Storage remains the persistence owner; the existing Core path preserves Mind Map synchronization. No natural-language command detection was added.
- Tests performed: Focused Flow, Mind Map workspace synchronization, and headless Flow GUI tests; full Python compilation; Git whitespace check.
- Known limitations: Creation stays explicit. Future Second Brain intent routing may offer natural-language creation only after its permission and command-routing boundary is designed.

## 2026-08-02 - Flow Read-Only Review Command

- Date: 2026-08-02
- Phase: Flow Chat review context
- Feature or fix: Added explicit read-only `/review <question>` patch review support.
- What changed: Added a Flow-owned builder that reads the Changelog and Future Implementations before current Git status, changed names, diff statistics, and bounded safe changed-file content. Missing review questions return local validation without an LLM call or Flow-history write.
- Files/modules affected: `flow_chat`, Core composition, focused Flow tests, Flow documentation, root future implementations, and this changelog.
- User-visible behavior: `/review <question>` asks AMADEUS the question with current bounded project review context. Normal Flow requests are unchanged.
- Architecture notes: `ProjectFileReader` remains the file-content boundary. Git is invoked read-only with no shell; the command never stages, commits, pushes, or reads ignored/runtime paths.
- Tests performed: `py -3 -m compileall .` completed; `py -3 -m unittest tests.test_flow_chat -v` passed 26 tests. The combined Flow/GUI run had one existing Canvas-shell failure caused by a fake Core without Canvas storage support.
- Known limitations: Git-unavailable repositories return an explicit context note. Review context is capped by file count and character limits and does not include staged-only diff content.

## 2026-08-02 - Creation Module V1

- Date: 2026-08-02
- Phase: Controlled creation handoff
- Feature or fix: Added source-derived metadata, categorization, and explicit Memory Brick proposal orchestration.
- What changed: Added a persistence-free Creation Module with strict Ollama JSON generation, source-hash checks, manual-field protection, temporary proposals, approval-only Memory writes, and duplicate-proposal rejection. Extended the existing Memory SQLite source table for caller-supplied raw content and derived metadata; approved records continue through JSONL compatibility and structured Memory Brick storage.
- Files/modules affected: `creation_module`, `memory_module`, Core composition, Mind Map synchronization, focused tests, module documentation, and this changelog.
- User-visible behavior: No GUI route was added. Public Core and module-registry facades are available for safe source registration and explicit approval workflows.
- Architecture notes: Creation owns orchestration only. Memory owns the sole database, JSONL compatibility, source metadata, and brick persistence. Raw locators are never dereferenced.
- Tests performed: Focused Creation/Memory tests and Python compilation.
- Known limitations: Generic registration requires the owner to supply raw content. No owner-specific source listings, proposal UI, background jobs, or autonomous extraction were added.

## 2026-08-02 - Structured Memory Foundation

- Date: 2026-08-02
- Phase: Memory Module foundation
- Feature or fix: Added additive SQLite structured memory storage beside the established JSONL memory store.
- What changed: Added Memory Bricks with multi-value labels, scope, evidence, importance, confidence, FTS/LIKE search, idempotent JSONL migration, source/layer/placeholder records, source-hash stale detection, a null vector boundary, and a Mind Map projection helper. Explicit `[memory]` saves now mirror into SQLite using the same ID.
- Files/modules affected: `memory_module`, focused memory-foundation tests, Memory Module documentation, and this changelog.
- User-visible behavior: Existing explicit memory saving, listing, prompt context, panels, and source-backed Mind Map editing remain unchanged. Structured retrieval and source registration are available through the module service; no automatic memory or derived content is created.
- Architecture notes: JSONL remains the compatibility path and canonical input for existing workflows. SQLite is module-owned at `data/memory/memory.sqlite`; source records retain metadata locators rather than copying module-owned raw data.
- Tests performed: Focused migration, dual-write, structured search, source-layer staleness, and Mind Map projection tests; changed-source compilation and existing Mind Map synchronization regression tests.
- Known limitations: Source adapters for existing module inventories and generated knowledge layers are intentionally deferred. The vector adapter is null until a local secondary index is selected.

## 2026-08-02 - Dedicated Chat Response Modes

- Date: 2026-08-02
- Phase: Dedicated Chat response-policy foundation
- Feature or fix: Added fixed per-chat response modes and backend output budgeting.
- What changed: Added canonical none, short, normal, large, and full_send policies; persisted response_mode metadata with normal migration; resolved each dedicated request once; injected safe policy instructions; mapped hard limits to Ollama num_predict; and suppressed NONE assistant bubbles and transcript rows.
- Files/modules affected: `response_modes`, Storage, Core coordinator, Chat Module, Ollama client, dedicated-chat metadata dialog, focused tests, module documentation, and this changelog.
- User-visible behavior: Edit or create a dedicated Chat and choose None, Short, Normal, Large, or Full Send. NONE processes the message but displays and stores no normal AMADEUS reply. Flow stays Normal.
- Architecture notes: Policies are independent immutable data. Core routes and resolves once, Chat builds prompts, Ollama applies the budget, Storage owns metadata, and the existing TraceLogger emits safe lifecycle metadata.
- Tests performed: Focused response-mode policy, storage migration, Core suppression, prompt/budget, and Ollama payload tests; changed-source compilation.
- Known limitations: Current non-streaming Ollama integration estimates completion from response size; a visible Full Send Continue action awaits a streaming/structured completion adapter.

## 2026-08-02 - Chat Transcript Spacing and Habit Matrix

- Date: 2026-08-02
- Phase: Chat and Habit Tracker visual polish
- Feature or fix: Restored the original chat alignment, added message spacing, and made Eisenhower task priority visible as a table.
- What changed: Flow Chat and dedicated Chats remain left-aligned, insert two empty transcript rows between messages, and render User/AMADEUS headings in bold. Dedicated Chat response length moved from the New/Edit Chat dialog to a title-only selector beneath Send. Habit Tracker highlights today's calendar date in light green and replaces its matrix list with Urgent, Important, and Task columns sorted by combined priority, urgent, important, then unmarked.
- Files/modules affected: `amadeus_gui/flow_chat_view.py`, `amadeus_gui/main/main_window.py`, `habit_tracker/view.py`, GUI and Habit Tracker documentation, focused tests, and this changelog.
- User-visible behavior: Chat messages are easier to scan without changing their established layout. The current calendar day is easy to find, and matrix priorities are visible at a glance.
- Architecture notes: These are display-only changes. Chat persistence, Core routes, and stored Eisenhower quadrant values remain unchanged.
- Tests performed: Focused transcript-spacing, calendar-format, and matrix-table checks plus changed-source compilation.
- Known limitations: Matrix indicator cells are read-only reflections of task creation choices; editing a task's priority after creation is not yet available.

## 2026-08-02 - Habit Tracker Weekly Routines

- Date: 2026-08-02
- Phase: Habit Tracker usability
- Feature or fix: Added weekday-selected recurring task creation to Habit Tracker.
- What changed: Added an `Add Routine` dialog with Monday-through-Sunday selectors. It stores selected days through the existing `custom_days` routine service contract, so one task record appears every matching weekday in each following week.
- Files/modules affected: `habit_tracker/view.py`, focused Habit Tracker tests and documentation, and this changelog.
- User-visible behavior: Dato can create a routine once, choose its weekly days, and check it off independently each time it recurs.
- Architecture notes: The UI reuses `HabitTrackerService.add_routine_task()` and its date-based recurrence evaluation; no recurring task copies are created.
- Tests performed: Habit Tracker service tests passed, including next-week Monday/Friday recurrence; headless PyQt6 dialog selection validation passed; changed files compiled successfully.
- Known limitations: The creation dialog currently covers custom weekly weekdays. Daily and every-other-day setup remain future UI options.

## 2026-08-02 - Habit Tracker Module Port

- Date: 2026-08-02
- Phase: Independent module integration
- Feature or fix: Replaced the Habit Tracker placeholder with the local Task Manager Personal task-planning workspace.
- What changed: Added an independent `habit_tracker` package with a local SQLite service and PyQt6 view for routine tasks, one-time tasks, calendar events, Eisenhower tasks, timers, and due-alarm notifications. Registered the real reusable view in the shared module-window shell. The source task manager's embedded AMADEUS chat panel, imports, and actions were intentionally excluded.
- Files/modules affected: `habit_tracker`, `amadeus_gui/main/main_window.py`, focused GUI/service tests, GUI and Habit Tracker documentation, and this changelog.
- User-visible behavior: Opening Habit Tracker now opens the complete local planning workspace in its own reusable window. AMADEUS chat remains exclusively in Flow Chat and is not duplicated inside Habit Tracker.
- Architecture notes: Habit Tracker owns only its local database at `data/habit_tracker/habit_tracker.db`; it has no Core, chat, memory, or external task-manager directory dependency.
- Tests performed: Habit Tracker service tests passed; a headless PyQt6 Habit Tracker view construction check passed; affected GUI shell tests were run.
- Known limitations: Routine creation and scheduled alarms/reminders existed in the source service but not its primary UI, so they remain service capabilities/future UI work. One existing Canvas GUI test fails with a fake Core that lacks Canvas storage support.

## 2026-08-02 - Core Public Shell Cleanup

- Date: 2026-08-02
- Phase: Core architecture cleanup
- Feature or fix: Separated the lightweight public Core entry point from the existing coordination implementation without changing Core behavior.
- What changed: Moved the complete existing `AmadeusCore` implementation into `core_coordinator.py` as `CoreCoordinator`. `core.py` now exposes the stable `AmadeusCore` type as a thin inherited public shell, so existing application, GUI, and test imports and method contracts remain unchanged.
- Files/modules affected: `amadeus_core/core.py`, `amadeus_core/core_coordinator.py`, Core documentation, and this changelog.
- User-visible behavior: None. All current Core routes, service attributes, payloads, and module facades are preserved.
- Architecture notes: The public entry point is now 12 lines and contains no feature logic. Composition and routing remain isolated behind the stable Core API, providing a safe foundation for future focused coordinator extractions.
- Tests performed: `py -3 -m compileall amadeus_core`; focused Core, annotation, Flow, project-file, materials, Mind Map workspace synchronization, and Mind Map annotation tests passed (71 tests).
- Known limitations: The existing Mind Map GUI busy-control test fails independently of this refactor. The required `python` command resolves to the unavailable Windows Store alias in this environment; validation used the installed `py -3` launcher.

## 2026-07-29 - Canvas Multi-Workspace Foundation

- Date: 2026-07-29
- Phase: Canvas project separation
- Feature or fix: Added lightweight Canvas workspaces so independent projects no longer share one overloaded infinite canvas.
- What changed: Added a versioned workspace registry, create/switch/rename/archive operations, one document per workspace, last-active restoration, safe migration of legacy root-level Canvas JSON files, recoverable trash storage, and per-workspace session undo. The Canvas GUI now exposes a workspace selector and New/Rename/Delete controls that are locked during active LLM requests.
- Files/modules affected: `canvas_module` models, storage, facade, GUI, focused tests and documentation; GUI feature/future documentation; this changelog.
- User-visible behavior: Dato can maintain separate Canvas projects, switch between them instantly, and reopen the last active workspace after restarting AMADEUS. Deleting a workspace archives its file and automatically leaves a valid active Canvas.
- Architecture notes: Workspace registry metadata is separate from Canvas document content. Stable workspace IDs survive renaming. Each workspace owns its blocks, connectors, root, semantic baseline, send operations, and undo stack.
- Tests performed: Focused tests cover creation, switching, renaming, independent data/baselines, last-active restoration, legacy migration, recoverable deletion, final-workspace replacement, per-workspace undo, malformed registry preservation, and title validation.
- Known limitations: Viewport centre/zoom are not yet stored per workspace, deleted workspaces do not yet have an in-app restore screen, and major modules still share the current stacked main-window shell.

## 2026-07-28 - Canvas Interaction and Direct-Answer Patch

- Date: 2026-07-28
- Phase: Canvas spatial conversation usability
- Feature or fix: Added persistent visual block resizing, two-right-click quick arrows, adaptive AMADEUS response sizing, and direct-answer prompt safeguards.
- What changed: Selected unlocked blocks display a bottom-right resize handle and save dimensions after the drag ends. Right-clicking a source block followed by a target block creates a directional arrow. Canvas prompts now contain human-readable target/history/peer text rather than raw object JSON and IDs. Metadata-narrating responses receive one corrective retry and are rejected if still unusable. Long AMADEUS responses start with a taller block while remaining manually resizable.
- Files/modules affected: `canvas_module/gui/view.py`, `canvas_module/conversation.py`, `canvas_module/canvas_module.py`, focused Canvas tests, Canvas documentation, and this changelog.
- User-visible behavior: Dato can resize text and AMADEUS blocks, create arrows rapidly with two right-clicks, and receive substantially cleaner answers that address the actual Canvas request rather than describing internal context objects.
- Architecture notes: Width/height remain layout-only and are excluded from semantic fingerprints. Connectors remain ID-based domain relationships. The exact structured context remains in the send audit record, while the LLM receives a concise semantic rendering.
- Tests performed: Focused tests cover direct prompts without IDs, corrective retry, metadata-response rejection, and adaptive long-response sizing. Full compilation and non-GUI regression validation are run with this delivery.
- Known limitations: Resize currently uses one bottom-right handle; undo/redo and multi-handle resizing remain future work.

## 2026-07-27 - Mind Map Import Schema Safeguard

- Date: 2026-07-27
- Phase: Mind Map reliability
- Feature or fix: Prevented unrelated JSON imports from clearing a Mind Map when replacement mode is selected.
- What changed: Mind Map imports now require the AMADEUS export schema: a non-empty `graph_id` plus `nodes` and `links` fields. Validation happens before node parsing and before the SQLite transaction, so a chat export JSON file is rejected without modifying graph data. Plain text imports continue to fail JSON parsing before any graph operation.
- Files/modules affected: `mindmap/service.py`, `tests/test_mindmap.py`, Mind Map documentation, root README, and this changelog.
- User-visible behavior: Choosing a chat JSON file or text file in Mind Map Import shows an error and leaves the current graph unchanged, including when Replace is selected.
- Architecture notes: The service owns the file-schema boundary. The repository continues to receive only fully validated `GraphNode` and `GraphLink` objects inside its atomic transaction.
- Tests performed: Focused Mind Map regression tests cover rejected chat JSON and text imports while preserving the existing graph. Full compile and test validation are run with this delivery.
- Known limitations: This does not reconstruct graph data already replaced by a prior empty import; recovery requires an earlier Mind Map JSON export or another backup.

## 2026-07-27 - Mind Map Callable Chat Retrieval

- Date: 2026-07-27
- Phase: Explicit Mind Map retrieval
- Feature or fix: Added bounded `[mindmap]` callable context for dedicated Chat.
- What changed: Added `[mindmap][search text] question` search retrieval and `[mindmap] question` recent-node retrieval, both limited to 10 nodes. The callable router formats only node ID, title, type, description, content, importance, confidence, and status as explicitly labeled Mind Map source context. No-match requests call the LLM with an explicit no-context block; retrieval failures return a safe response without an LLM call. Empty-query retrieval now uses the public SQL-bounded `list_recent_nodes()` facade rather than materializing the full graph.
- Files/modules affected: `annotation_module`, `amadeus_core`, `mindmap`, `amadeus_chat`, focused annotation tests, root/module documentation, and this changelog.
- User-visible behavior: Dato can ask Chat about explicit bounded Mind Map data without manually copying nodes into the prompt.
- Architecture notes: Core injects the registered `MindMapModule` facade into `CallableContextRouter`; search uses `search_nodes()` and empty retrieval uses `list_recent_nodes()`, which accepts a validated 1 to 100 node limit in the service and repository SQL query. Chat and Annotation Module do not access graph SQLite, repositories, links, source references, or arbitrary node metadata. Process events use generic summaries and exclude query/node values and raw errors.
- Tests performed: Focused parser, Core annotation, and Mind Map callable retrieval tests passed. Full suite and compile validation are run with this delivery.
- Known limitations: Recent retrieval is intentionally capped at 100 nodes; broader semantic and graph-traversal retrieval remain future work.

## 2026-07-27 - Mind Map Legacy Visual and Rendering Performance Port

- Date: 2026-07-27
- Phase: Mind Map GUI visual compatibility and performance
- Feature or fix: Ported the legacy Mind Map workspace styling and removed ordinary-refresh scene recreation.
- What changed: Restored the legacy dark title/subtitle/status typography, framed Nodes/Actions, Graph Space, and Context/Node Details panel hierarchy, palette, spacing, borders, and grouped controls. Snapshot rendering now reconciles graph items by ID. Visual-only force motion uses a bounded 33 ms timer that settles and stops; live motion and synchronous auto-layout have 120- and 80-node caps respectively.
- Files/modules affected: `mindmap/gui/view.py`, `mindmap/gui/items.py`, `mindmap/gui/physics.py`, focused Mind Map tests, Mind Map documentation, and this changelog.
- User-visible behavior: The page visually matches the legacy workspace while ordinary refreshes retain existing graph items and large graphs avoid GUI-thread force-layout stalls.
- Architecture notes: Core-only, QThread, SQLite, and identifier-only notification boundaries remain unchanged. Legacy direct filesystem source open/edit behavior remains excluded. Timer positions are transient and never persisted.
- Tests performed: Focused `py -3 -m unittest tests.test_mindmap` and `py -3 -m compileall mindmap tests` passed; full suite and full compile validation are run with this delivery.
- Known limitations: Layout above 80 nodes is intentionally declined until a background layout engine is implemented.

## 2026-07-27 - Mind Map Position Lock Semantics

- Date: 2026-07-27
- Phase: Mind Map GUI adaptation review
- Feature or fix: Prevented false pin metadata from overriding a persistent node position lock.
- What changed: Graph physics, service single and batch moves, and scene persistence/layout filters now treat `position_locked` and `mindmap_pinned` as additive locks.
- Files/modules affected: `mindmap/gui/physics.py`, `mindmap/gui/view.py`, `mindmap/service.py`, focused Mind Map tests, Mind Map documentation, and this changelog.
- User-visible behavior: Nodes with `position_locked=True` cannot be dragged, force-laid out, recentered, or batch-moved even when `mindmap_pinned=False`.
- Architecture notes: The persistent model lock remains authoritative; metadata pinning adds an independent temporary layout lock.
- Tests performed: Focused Mind Map tests, explicit `tests` discovery suite, and compile validation passed.
- Known limitations: Force layout remains the bounded V1 simulation; broader graph batch creation and advanced layout engines remain future work.

## 2026-07-27 - Mind Map Port Review Fixes

- Date: 2026-07-27
- Phase: Mind Map GUI adaptation review
- Feature or fix: Hardened force layout, pin behavior, source metadata refreshes, graph subscriptions, and layout persistence.
- What changed: Co-located nodes now receive a deterministic nonzero force direction. Metadata-pinned nodes are immovable in both scene interaction and persistence. Source-node upserts preserve existing `mindmap_pinned` and `mindmap_central` metadata. Graph subscriptions now return unsubscribe callbacks that views invoke on close or destruction. Canvas input is disabled during workers. Layout and recenter coordinate changes use a Core-mediated atomic batch repository transaction.
- Files/modules affected: `mindmap/gui`, `mindmap/service.py`, `mindmap/repository.py`, `mindmap/mind_map_module.py`, `amadeus_core/core.py`, focused Mind Map tests, Mind Map documentation, and this changelog.
- User-visible behavior: Pinned nodes cannot be dragged, auto-layout reliably separates overlapping nodes, and the canvas cannot accept conflicting input while graph work runs.
- Architecture notes: View metadata ownership remains in the service layer; no GUI-side merge is required. Batch coordinate persistence remains behind Core and the Mind Map module facade.
- Tests performed: Focused Mind Map tests, full test suite, and compile validation are run with this delivery.
- Known limitations: Force layout remains the bounded V1 simulation; broader graph batch creation and advanced layout engines remain future work.

## 2026-07-27 - Mind Map PyQt6 Core-Safe Visual Port

- Date: 2026-07-27
- Phase: Mind Map GUI adaptation
- Feature or fix: Replaced the initial graph page layout with the approved force-directed three-panel PyQt6 workspace.
- What changed: Added deterministic in-memory graph physics, type-coloured relevance/importance-sized nodes, pan/zoom/drag, selected and hover context, grouped node listing, Actions controls, Context/Node Details tabs, pin/central metadata controls, linked recentering, focus, and Core-worker-backed CRUD/link/layout actions.
- Files/modules affected: `mindmap/gui`, focused Mind Map tests, Mind Map documentation, and this changelog.
- User-visible behavior: Mind Map is now a three-panel force-graph workspace while JSON import/export, search, property editing, and Core-backed persistence remain available.
- Architecture notes: Physics never accesses SQLite or persists automatically. All graph reads and mutations remain Core-mediated QThread work; pin/central are existing node metadata updates; invalidation notices remain identifier-only.
- Tests performed: Focused Mind Map tests and `py -3 -m compileall mindmap tests` passed; full discovery is recorded with this delivery.
- Known limitations: Legacy direct source-file opening, source-derived previews, source-file editing, and global window behaviors were intentionally excluded for privacy, containment, and Core-boundary safety.

## 2026-07-27 - Mind Map Safety Hardening

- Date: 2026-07-27
- Phase: Mind Map V1 safety review fixes
- Feature or fix: Made replacement imports atomic, redacted live subscriptions, contained SQLite paths, and moved graph work off the GUI thread.
- What changed: Import records are fully validated before one repository transaction writes them; replacement failures preserve the old graph. Core subscriptions now publish identifier-only invalidation notices. The Mind Map page uses QThread workers with busy controls and GUI-thread rendering for snapshots, mutations, search, import/export, and layout persistence. Database paths reject absolute and escaping relative paths.
- Files/modules affected: `mindmap`, `amadeus_core`, focused Mind Map tests, module/Core documentation, and this changelog.
- User-visible behavior: Import failures leave the existing graph intact; the Mind Map remains responsive during SQLite and JSON work, with controls recovering after errors.
- Architecture notes: Public notifications carry no graph fields or arbitrary metadata; GUI data continues to come from Core snapshots. SQLite remains module-owned and per-operation connections remain thread-safe.
- Tests performed: Focused Mind Map Core/repository and offscreen PyQt worker tests, full suite, and compile validation are recorded with this delivery.
- Known limitations: Imports and exports intentionally retain V1 user-selected file locations; only the module-managed SQLite database path is project-root-contained.

## 2026-07-27 - Chat Registry V2

- Date: 2026-07-27
- Phase: Chat Registry V2
- Feature or fix: Added validated dedicated-chat priority, purpose, and descriptive scope metadata.
- What changed: Extended the existing chat JSON index and `ChatMetadata`, Core wrappers, Registry projection, Flow metadata formatting, and create/edit dialog. Legacy rows safely default to Normal/General/Local; invalid API values raise `ValueError`.
- Files/modules affected: `storage`, `chat_registry`, `flow_chat`, `amadeus_core`, `amadeus_gui`, focused tests, module/root documentation, and this changelog.
- User-visible behavior: New and existing chats can display and edit priority, purpose, and scope. Flow sees those metadata fields but never message bodies.
- Architecture notes: No second registry or database was created. Scope remains descriptive in V1 and does not cause automatic cross-chat retrieval.
- Tests performed: Focused Flow/storage/registry/Core and offscreen GUI tests, full unittest discovery, and compile validation are recorded with this delivery.
- Known limitations: Scope has no retrieval behavior; any future cross-chat content access requires explicit user selection and permissions.

## 2026-07-27 - Mind Map: Core And GUI Integration

- Date: 2026-07-27
- Phase: Mind Map integration
- Feature or fix: Integrated the imported local Mind Map / Relevance Graph package through Core and replaced only the Mind Map GUI placeholder.
- What changed: Core now constructs/registers `mind_map` and exposes graph snapshot, CRUD, move, search, neighborhood, source-upsert, import/export, and subscription wrappers. The stacked Mind Map page now uses `MindMapView`. Mutation events use truthful generic lifecycle summaries and generic failure terminals without private graph values or raw errors. Added Mind Map runtime Git ignore and `unittest` Core/GUI coverage.
- Files/modules affected: `mindmap`, `amadeus_core`, `amadeus_gui`, `.gitignore`, focused tests, root/module documentation, and this changelog.
- User-visible behavior: Mind Map navigation opens the persistent interactive graph canvas with local SQLite nodes/links, layout controls, search, and JSON import/export; other pages and navigation remain unchanged.
- Architecture notes: GUI graph calls terminate at Core. Core delegates to the registered module facade; SQLite and PyQt scene ownership remain within Mind Map. Live subscriptions remain fault-isolated and process events omit titles, labels, contents, user errors, backend details, and hidden reasoning.
- Tests performed: Focused Mind Map/Core and offscreen GUI tests, full unittest discovery, and compile validation are run with this delivery.
- Known limitations: Source-opening adapters, undo/redo, multi-graph workspaces, and automated graph creation remain future work.

## 2026-07-27 - Process Monitor: Safe Global Enrichment

- Date: 2026-07-27
- Phase: Process Monitor enrichment
- Feature or fix: Added truthful, granular request events across normal chat, Flow, Side Ask, and callable annotation routes.
- What changed: Added the `TraceLogger.add_plan()` native `PLAN` API for declared route intent, source-specific context load events, configured-LLM response composition events, successful persistence events, and fallback response-path terminal finalization.
- Files/modules affected: `amadeus_trace`, `amadeus_core`, `context_builder`, `amadeus_chat`, `flow_chat`, `annotation_module`, focused tests, and module documentation.
- User-visible behavior: The Process Monitor now names work that actually occurred, such as loading recent history, selecting project overview, loading explicit memory, preparing an answer through the configured LLM, and storing a completed exchange.
- Architecture notes: Plans describe only declared code routes. Events exclude user messages, prompt/context bodies, model responses, hidden reasoning, and backend error details; run IDs, sequences, listener isolation, and terminal rejection remain emitter-owned.
- Tests performed: Focused process, normal-chat/annotation, and Flow tests plus full suite and compile validation are run with this delivery.
- Known limitations: Events remain in-memory per request; trace export, persistence, and Process Monitor V2 filtering/timeline remain future work.

## 2026-07-27 - Flow Chat: Documentation

- Date: 2026-07-27
- Phase: Flow Chat GUI Shell - Task 4
- Feature or fix: Documented current Flow Chat behavior and boundaries.
- What changed: Updated root, GUI, Chat, and Core documentation; added Flow module documentation covering the navigation shell, separate Flow storage, Layer 0 Flow history, Layer 1 metadata-only registry context, live metadata mutations, and shared Process Monitor events.
- Files/modules affected: Root README, `amadeus_gui`, `amadeus_chat`, `amadeus_core`, `flow_chat`, and this changelog.
- User-visible behavior: Documentation now states that AMADEUS starts on Flow, dedicated Chats remain separate, and Code, Mind Map, and Habit Tracker are foundation-pending pages.
- Architecture notes: Flow receives only dedicated-chat `chat_id`, title, and description, never message bodies; shared events remain diagnostic-only and Core-mediated.
- Tests performed: Documentation-only change; no runtime tests run.
- Known limitations: Dedicated-chat content retrieval, Flow token-aware history budgeting, and functional Code, Mind Map, and Habit Tracker routes are not implemented.

## 2026-07-27 - Flow Chat: GUI Shell

- Date: 2026-07-27
- Phase: Flow Chat GUI Shell - Task 3
- Feature or fix: Added the persistent Flow Chat home and navigation shell.
- What changed: The main window now retains five sidebar pages: Flow Chat, the existing dedicated Chats surface, and named Code, Mind Map, and Habit Tracker foundations. Flow loads Core-provided history, sends requests through a QThread worker to `handle_flow_message`, streams Process Monitor events, and recovers its input after safe failures.
- Files/modules affected: `amadeus_gui`, `amadeus_core`, focused headless GUI tests, and GUI documentation.
- User-visible behavior: AMADEUS opens on Flow Chat; switching pages preserves each page's widgets and drafts. Dedicated-chat controls and its right-side workspace remain available under Chats.
- Architecture notes: Flow history crosses the GUI boundary through `AmadeusCore.load_flow_history`; the GUI does not access Flow storage. Dedicated chat retains its existing right-panel renderer, while Flow has a focused event-only Process Monitor to avoid exposing dedicated-chat workspace actions.
- Tests performed: `py -3 -m unittest tests.test_flow_chat_gui -v`, `py -3 -m unittest tests.test_annotation_gui -v`, and `py -3 -m compileall .` passed.
- Known limitations: Code, Mind Map, and Habit Tracker are intentional named placeholders pending independent module routes.

## 2026-07-27 - Flow Chat: Task 2 Review Fixes

- Date: 2026-07-27
- Phase: Flow Chat GUI Shell - Task 2 review fixes
- Feature or fix: Made Flow exchange persistence atomic and hardened Flow failures.
- What changed: Flow now builds both exchange records before one locked atomic replacement, uses an explicit LLM execution result instead of Process Monitor state to decide persistence, and returns a generic safe Flow failure payload for failed execution or unexpected exceptions.
- Files/modules affected: `flow_chat`, `amadeus_chat`, `amadeus_core`, and focused Flow tests.
- User-visible behavior: Failed Flow requests do not expose backend errors or add partial history; normal chat behavior is unchanged.
- Architecture notes: Process Monitor remains diagnostic-only. Flow execution outcome is independent of trace event recording or listener delivery.
- Tests performed: Focused Flow, Core/process-event tests, and compile validation are recorded with this delivery.
- Known limitations: Flow still exposes dedicated-chat metadata only; token-aware history trimming is not implemented.

## 2026-07-27 - Flow Chat: Context And Core Route

- Date: 2026-07-27
- Phase: Flow Chat GUI Shell - Task 2
- Feature or fix: Added the isolated Flow context builder, execution service, and Core request route.
- What changed: Flow now builds bounded Flow-only history plus separately formatted `[AVAILABLE DEDICATED CHATS]` metadata from the metadata-only registry. Core routes Flow requests through the existing Chat module and identity builder, emits ordered shared lifecycle events, and stores only successful Flow user/assistant exchanges.
- Files/modules affected: `flow_chat`, `amadeus_core`, focused Flow tests, and Core documentation.
- User-visible behavior: Flow requests return the normal response payload with Flow-specific Process Monitor events while dedicated chat behavior and history remain unchanged.
- Architecture notes: Dedicated-chat bodies are not loaded by Flow context. Core retains trace lifecycle and event-listener ownership; Flow service owns Flow context coordination and isolated persistence.
- Tests performed: `py -3 -m unittest tests.test_flow_chat -v` passed 12 tests. Full compile validation is recorded with the task delivery.
- Known limitations: Flow exposes metadata only; explicit dedicated-chat content retrieval and token-aware history budgeting are not implemented.

## 2026-07-14 - Shared Process Events: Foundation Documentation And Release

- Date: 2026-07-14
- Phase: Shared Process Events - Task 4
- Feature or fix: Documented and released the shared process-event foundation only.
- What changed: Documented the immutable validated event model, emitter lifecycle and listener API, normal-chat live GUI bridge, safety boundary, and `TraceLogger` compatibility facade. Updated future scope to retain Process Monitor V2, Inner Brain, and persistent background jobs as future work.
- Files/modules affected: `amadeus_trace` documentation, `amadeus_gui` documentation, global changelog, and Task 4 report.
- User-visible behavior: Process Monitor documentation now accurately describes incremental normal-chat event display followed by final-payload reconciliation; no new runtime behavior is introduced by this release task.
- Architecture notes: `ProcessEventEmitter` remains framework-independent and listener failures remain isolated. Core exposes a framework-neutral listener while the GUI worker performs the PyQt adaptation. This is the foundation only, not Process Monitor V2, an Inner Brain, or persistent job tracking.
- Tests performed: `python` was unavailable through the Windows App Execution Alias, so `py -3 -m compileall .` completed successfully and `py -3 -m unittest discover -s tests -v` passed 62 tests; details are recorded in `.superpowers/sdd/shared-events-task-4.md`.
- Known limitations: Process Monitor V2 filtering/timeline, trace export and persistence, any Inner Brain presentation, and persistent background-job tracking are not implemented.

## 2026-07-14 - Shared Process Events: Task 2 Failure Lifecycle Fixes

- Date: 2026-07-14
- Phase: Shared Process Events - Task 2 review fixes
- Feature or fix: Completed safe terminal handling for LLM and missing-chat failures.
- What changed: Chat emits a generic failed LLM response event without error-body text. Core detects module failure events and finalizes the run as failed; the missing-chat branch now also emits the same terminal failure.
- Files/modules affected: `amadeus_core`, `amadeus_chat`, `amadeus_trace`, lifecycle tests, module documentation, changelog, and Task 2 report.
- User-visible behavior: Existing detailed LLM and missing-chat response strings are unchanged, while Process Monitor events remain safe and terminally accurate.
- Architecture notes: Chat owns the LLM boundary event; Core retains ownership of the final run state through the TraceLogger facade.
- Tests performed: Recorded in `.superpowers/sdd/shared-events-task-2.md`.
- Known limitations: Live GUI event forwarding remains Task 3.

## 2026-07-14 - Shared Process Events: Active Chat Lifecycle

- Date: 2026-07-14
- Phase: Shared Process Events - Task 2
- Feature or fix: Added genuine normal active-chat lifecycle events.
- What changed: Core now reports receipt, route, and terminal result/failure; Context Builder reports context start and safe selected-type completion; Chat reports LLM request and response boundaries. `TraceLogger` now provides safe terminal facade methods.
- Files/modules affected: `amadeus_core`, `context_builder`, `amadeus_chat`, `amadeus_trace`, focused lifecycle tests, module documentation, and Task 2 report.
- User-visible behavior: Normal chat returns one ordered Process Monitor lifecycle without prompt bodies, context values, or LLM response text.
- Architecture notes: Lifecycle ownership remains at the actual Core, Context Builder, and Chat execution boundaries; no GUI integration was added.
- Tests performed: Recorded in `.superpowers/sdd/shared-events-task-2.md`.
- Known limitations: Events are returned with the completed Core response; live GUI forwarding is Task 3.

## 2026-07-14 - Shared Process Events: Legacy Empty Session Fix

- Date: 2026-07-14
- Phase: Shared Process Events - Task 1
- Feature or fix: Restored empty legacy trace sessions.
- What changed: `TraceLogger.start_session()` now starts its emitter run without recording a synthetic event; direct `ProcessEventEmitter.start_run()` retains its initial running event by default.
- Files/modules affected: `amadeus_trace`, focused process-event tests, trace feature documentation, changelog, and Task 1 report.
- User-visible behavior: A newly started legacy Process Monitor session remains empty until code adds its first trace event.
- Architecture notes: Silent start is an opt-in emitter parameter used by the compatibility facade only.
- Tests performed: Recorded in the appended Task 1 report.
- Known limitations: Active-chat lifecycle ownership and live GUI delivery remain separate follow-up tasks.

## 2026-07-14 - Shared Process Events: Task 1 Review Fixes

- Date: 2026-07-14
- Phase: Shared Process Events - Task 1
- Feature or fix: Preserved legacy trace categories and made run terminal states enforceable.
- What changed: `TraceLogger` now retains normalized legacy categories for compatibility rendering while still publishing validated event fields. Completed and failed runs reject later events and duplicate/conflicting terminal lifecycle calls.
- Files/modules affected: `amadeus_trace`, focused process-event tests, trace feature documentation, changelog, and Task 1 report.
- User-visible behavior: Existing detailed trace text and structured payloads keep `file`, `llm`, `annotation`, `module`, and `routing` labels.
- Architecture notes: The legacy category is compatibility metadata owned by the facade; the event model continues to use validated types. Terminal state is reset only by a new run.
- Tests performed: Recorded in the appended Task 1 report.
- Known limitations: Active-chat lifecycle ownership and live GUI delivery remain separate follow-up tasks.

## 2026-07-14 - Shared Process Events: Task 1 Foundation

- Date: 2026-07-14
- Phase: Shared Process Events - Task 1
- Feature or fix: Added validated framework-independent process-event recording and legacy trace compatibility.
- What changed: Added immutable `ProcessEvent` records, validated enums, ordered run lifecycle emission, fault-isolated subscriptions, and a `TraceLogger` facade that maps legacy category/level calls to the emitter while retaining historic text and payload aliases.
- Files/modules affected: `amadeus_trace`, focused process-event tests, and trace documentation.
- User-visible behavior: Existing Process Monitor trace text and legacy structured fields remain available; the backend can now provide validated ordered events to later lifecycle and GUI work.
- Architecture notes: `ProcessEventEmitter` has no PyQt dependency and is the source of truth for `TraceLogger` payload output. Core/module lifecycle ownership and GUI live delivery are intentionally not included.
- Tests performed: `py -3 -m unittest tests.test_process_events tests.test_annotation_core -v` passed; full discovery and compile checks are recorded in the Task 1 report.
- Known limitations: Active-chat code does not yet emit the complete lifecycle, and no GUI listener bridge has been added.

## 2026-07-14 - Phase 6 Follow-Up: Comment Target And Jump Fixes

- Date: 2026-07-14
- Phase: Phase 6 - Comments And Export Display Polish
- Feature or fix: Preserved unknown selection-comment identity and hardened comment message jumps.
- What changed: Selection comments without a detected message number now display as `Comment(?)`, retain Selection target details, and keep Jump disabled; `Comment(A)` remains exclusive to general comments. MainWindow now finds only document blocks beginning with the requested rendered message header, preventing content text such as `[12] ` from receiving the jump.
- Files/modules affected: `comments_module`, `amadeus_gui`, focused comment/GUI tests, and Phase 6 module documentation.
- User-visible behavior: Unknown selected-text comments are no longer presented as general chat comments. Jump always lands on the actual visible numbered-message header or reports it unavailable.
- Architecture notes: Comment type continues to determine comment semantics while message number remains optional best-effort metadata. GUI jump lookup uses QTextDocument block boundaries rather than an unanchored text search.
- Tests performed: `py -3 -m unittest tests.test_comments_module -v` passed 5 tests; `py -3 -m unittest tests.test_annotation_gui -v` passed 12 tests; `py -3 -m unittest discover -s tests -v` passed 44 tests; `py -3 -m compileall .` completed successfully.
- Known limitations: Selection message detection remains best-effort until exact structured message references exist; unknown selections intentionally cannot jump.

## 2026-07-14 - Phase 6: Comments And Export Display Polish

- Date: 2026-07-14
- Phase: Phase 6 - Comments And Export Display Polish
- Feature or fix: Completed general and selection comment actions plus clean exported-chat presentation in Materials.
- What changed: Added general chat comments alongside selection comments, edit/delete/jump actions in the Comments panel, and clean `Comment(number)` and `Comment(A)` headings. Export records now retain optional first/last message bounds for clean date and range rows, opened export content omits internal ids, and Export Materials exposes Open, Use, Copy Path, and Delete actions.
- Files/modules affected: `comments_module`, `export_module`, `materials_module`, `amadeus_core`, `amadeus_gui`, focused tests, and Phase 6 module documentation.
- User-visible behavior: Users can add a comment without selecting text, manage saved comments, and jump to a visible selected-message target. Materials presents exported chats with readable dates/ranges and direct export-specific controls.
- Architecture notes: Comment types and edit/delete operations remain owned by Comments through Core-mediated GUI calls. Materials composes Export's public API and uses display-ready export metadata; old export records safely fall back to message counts when bounds are absent.
- Tests performed: `python` resolves to the Windows App Execution Alias, so `py -3 -m compileall .` completed successfully. `py -3 -m unittest discover -s tests -v` passed 41 tests.
- Known limitations: Selection message detection remains best-effort until exact `[current][number]` references exist. Jump works only for messages currently visible in the chat, and legacy exports without saved bounds show message counts rather than exact ranges.

## 2026-07-13 - Phase 5: Managed Materials

- Date: 2026-07-13
- Phase: Phase 5 - Managed Materials
- Feature or fix: Replaced the Materials placeholder with managed references and export records.
- What changed: Materials lists managed local text files and existing exports with id/name/type/metadata, supports non-injecting preview/open, explicit one-request callable context, reference copying, and deliberate removal. The GUI provides selection, Preview, Open, Use in Next Message, Ask AMADEUS, Remove, Refresh, and Copy Ref controls.
- Files/modules affected: `materials_module`, `export_module`, `amadeus_core`, `amadeus_gui`, focused tests, and module documentation.
- User-visible behavior: Selecting or opening a material never changes chat context. Use applies only to the next sent message; Ask always identifies the selected material explicitly.
- Architecture notes: GUI receives material rows and content only from Core. Materials composes the Export module's public API; export annotations and TXT/Markdown/JSON compatibility remain unchanged.
- Tests performed: `py -3 -m compileall .` completed successfully; `py -3 -m unittest discover -s tests -v` passed 23 tests. `python` is unavailable on PATH, so the installed Windows launcher was used.
- Known limitations: Managed materials currently support UTF-8 text files already placed under `data/materials/`; upload, PDF, image, and search workflows remain future work.

## 2026-07-13 - Code Viewer Explicit File Context

- Date: 2026-07-13
- Phase: Phase 4 - Exact Code Access and Interactive Code Viewer
- Feature or fix: Added line-labelled code display and explicit range-limited file context for direct questions.
- What changed: Code Viewer now renders one-based line labels. Removed the Use in Next Message workflow. Ask AMADEUS About File now has a default-off context toggle and optional `15` or `15-30` selector; Project File Reader validates ranges and builds exact line-labelled context only when Core is instructed to include it.
- Files/modules affected: `amadeus_gui`, `amadeus_core`, `project_file_reader`, focused tests, and Phase 4 documentation.
- User-visible behavior: Opened files remain visual by default. Enabling context sends only the selected verified file or range with a direct file question.
- Architecture notes: GUI still delegates through Core; Core delegates range validation and content formatting to Project File Reader. No selected-file context is retained for later normal messages.
- Tests performed: `py -3 -m compileall .` completed successfully; `py -3 -m unittest discover -s tests -v` passed 19 tests.
- Known limitations: Code Viewer does not yet provide syntax highlighting.

## 2026-07-13 - Code Viewer Browser Polish

- Date: 2026-07-13
- Phase: Phase 4 - Exact Code Access and Interactive Code Viewer
- Feature or fix: Made Code Viewer filenames fully visible and the project browser collapsible.
- What changed: Disabled tree text elision, enabled horizontal scrolling for long paths, and placed project navigation inside a collapsed-by-default Project Browser control.
- Files/modules affected: `amadeus_gui/side/side_panel.py`, GUI documentation, and `AMADEUS_CHANGELOG.md`.
- User-visible behavior: Opened code receives more panel space by default; expand Project Browser only when navigating. Long filenames remain readable instead of ending with ellipses.
- Architecture notes: GUI-only presentation change; the trusted project file service and Core routing remain unchanged.
- Tests performed: `py -3 -m compileall .` and `py -3 -m unittest tests.test_annotation_gui -v` completed successfully.
- Known limitations: Very long paths may require horizontal scrolling within the project browser.

## 2026-07-13 - Phase 4: Project File Navigation

- Date: 2026-07-13
- Phase: Phase 4 - Project File Navigation
- Feature or fix: Added guarded full project-root Code Viewer navigation and explicit one-shot selected-file context.
- What changed: Project File Reader now supplies root-relative directory trees and metadata, size-limited binary-safe text reads with explicit decoding fallbacks, and module read delegation through the same trusted reader. Core exposes tree/open/select/ask APIs. The Code Viewer now has lazy tree expansion, filtering, refresh, path copying, and selected-file actions.
- Files/modules affected: `project_file_reader`, `amadeus_core`, `amadeus_gui`, focused tests, and Phase 4 documentation.
- User-visible behavior: Users can browse and open safe project files from Code Viewer, copy their relative paths, use a selected file in exactly the next normal message, or ask about it directly.
- Architecture notes: GUI filesystem signals terminate at Core; Core delegates to Project File Reader. Selected-file content remains process-local, callable context and is consumed once rather than persisted or automatically injected.
- Tests performed: `py -3 -m compileall .` completed successfully; `py -3 -m unittest discover -s tests -v` passed 17 focused parser, Core, GUI keyboard, project-reader, and temporary-context tests.
- Known limitations: Tree loading is direct-directory lazy expansion without project-wide search, syntax highlighting, modified-time metadata, or recursive depth controls.

## 2026-07-13 - Phase 3: Annotation Engine V2

- Date: 2026-07-13
- Phase: Phase 3 - Annotation Engine V2
- Feature or fix: Added independent annotation blocks anywhere in a complete message.
- What changed: The Annotation Module extracts ordered `[annotation] ... [end]` blocks, Core executes deterministic results as callable context for outside-block prompt text, and the GUI supports keyboard suggestion selection plus an `[end]` suggestion.
- Files/modules affected: `annotation_module`, `amadeus_core`, `amadeus_gui`, focused `tests`, and Phase 3 documentation.
- User-visible behavior: Users can combine multiple annotation blocks with ordinary prompt text; only ordinary text outside blocks is sent as the normal chat request. Up/Down, Enter/Tab, and Escape control visible suggestions.
- Architecture notes: Block grammar remains entirely parser-owned. Core consumes structured parser output and retains the legacy unclosed leading annotation route for compatibility.
- Tests performed: `py -3 -m compileall .` completed successfully; `py -3 -m unittest discover -s tests -v` passed 13 focused parser, Core, and offscreen GUI keyboard tests.
- Known limitations: Multiple blocks can return only the latest side-panel payload, and block results currently enter callable context as labelled text rather than typed provenance.

## 2026-07-13 - Phase 2: Lightweight Core and GUI Separation

- Date: 2026-07-13
- Phase: Phase 2 - Lightweight Core and GUI Separation
- Feature or fix: Established main/side GUI package ownership and moved active callable sheet/export routing into the Annotation Module.
- What changed: Moved the main window to `amadeus_gui.main`, moved right-side workspace rendering to `amadeus_gui.side`, and added `CallableContextRouter` for `[sheet]` and `[export]` prompt routes.
- Files/modules affected: `amadeus_gui`, `amadeus_core`, `annotation_module`, and their Phase 2 documentation.
- User-visible behavior: No intentional visible behavior changes. The existing window, controls, tabs, annotations, and response payloads retain their behavior.
- Architecture notes: Core delegates active callable annotation feature logic through injected module public APIs. GUI startup continues to use the stable `amadeus_gui.AmadeusMainWindow` import, avoiding circular imports.
- Tests performed: `py -3 -m compileall .` completed successfully. Core and GUI import/initialization validation completed successfully after the package move.
- Known limitations: This controlled slice leaves inactive legacy callable sheet/export helper bodies in Core until focused router tests are available. Other GUI responsibilities remain in `main_window.py` until each has a clear independent boundary.

## 2026-07-13 - Phase 1: Repository Safety and Development Baseline

- Date: 2026-07-13
- Phase: Phase 1 - Repository Safety and Development Baseline
- Feature or fix: Protected private runtime data from future Git tracking and hardened the AMADEUS Git workflow.
- What changed: Ignored chats, comments, memory, sheets, and exports; removed previously tracked runtime files from the Git index without deleting local data; replaced automatic blanket staging with reviewed intended-path staging; and standardized changelog requirements.
- Files/modules affected: `.gitignore`, `AGENTS.md`, `.opencode/commands/push-checkpoint.md`, `README.md`, `AMADEUS_CHANGELOG.md`, and the Git index entries below `data/`.
- User-visible behavior: Existing local chats, comments, memory, sheets, and exports remain available to AMADEUS but no longer appear as future Git changes.
- Architecture notes: Storage modules continue to own and create runtime directories. No Core, GUI, or module business logic changed.
- Tests performed: `py -3 -m compileall .` completed successfully. `python -m compileall .` could not run because `python` is not on `PATH`; the installed Windows Python launcher provided the equivalent validation.
- Known limitations: Private runtime contents remain in historical commits already pushed before this phase. This phase protects future commits only and does not rewrite history.

## 2026-07-02 - Identity Module
- Added AMADEUS Identity Module.
- Injected global identity into normal chat prompts.
- Added `[identity]` inspection commands.

## 2026-07-02 - Context History
- Added recent conversation context so AMADEUS can refer to previous messages in the active chat.
- Moved context-selection responsibility into `context_builder`.

## 2026-07-02 - Process Monitor
- Added `amadeus_trace` module.
- Added right-side Process Monitor with Compact/Detailed trace display.

## 2026-07-02 - Documentation and Comment Rules
- Added project workflow rule: update module feature/future docs for every feature change.
- Added project workflow rule: code comments must explain architecture, ownership, flow, and safety boundaries.

## 2026-07-02 - File Annotation and Code Viewer
- Separated normal chat summary/explanation mode from exact `[file]` mode.
- Added guided annotation suggestions.
- Added right-side Code Viewer for exact file contents.
- Added multiline input: Enter sends, Shift+Enter inserts a newline.

## 2026-07-02 - Multi-Chat V1
- Added chat selector, New Chat, and Delete Chat controls.
- Added per-chat JSONL history files and chat index storage.

## 2026-07-02 - Memory V1
- Added `memory_module`.
- Added `[memory][global]`, `[memory][chat]`, and `[memory][list]`.
- Added right-side Memory panel.
- Added global/chat memory prompt injection.

## 2026-07-02 - Chat Workspace V2
- Added visible message numbers in the chat view.
- Added New Chat dialog with title and description.
- Added chat metadata fields for title, description, and reserved summary.
- Added current chat context display in the Memory panel.
- Added active chat workspace context injection through Context Builder.
- Added global root tracking files: `AMADEUS_CHANGELOG.md` and `AMADEUS_FUTURE_IMPLEMENTATIONS.md`.

## 2026-07-02 - Side Panel Foundation
- Added dedicated `side_panel` module for right-panel payload/state structure.
- Added reusable `amadeus_gui/right_panel_widget.py` for Process Monitor, Code Viewer, and Memory tabs.
- Refactored `amadeus_gui/main_window.py` so it coordinates the window instead of owning every side-panel rendering detail.
- Prepared a clean foundation for future `[panel]`, sheets, materials, diff viewer, and current-context panel support.

## 2026-07-02 - Sheets V1 + Materials Panel Foundation

- Added `sheets_module` for editable global/chat-scoped sheets.
- Added local sheet storage at `data/sheets/sheets.json`.
- Added a right-side `Sheets` tab with direct editing, creation, saving, and deletion.
- Added `[sheet]` annotation for listing/opening sheets and injecting selected sheet context into a prompt.
- Added annotation suggestions for `[sheet]`, `[sheet][chat]`, `[sheet][global]`, and visible sheet titles.
- Added `materials_module` foundation and right-side `Materials` tab.
- Documented the future export annotation plan: `[export][chat name][4-6]` for selected message-number segments.
- Kept exact sheet content callable rather than always-active memory to protect prompt cleanliness.

## Chat Export V1 Patch

- Added `export_module/` for deterministic chat exports.
- Added TXT, Markdown, and JSON export files under `data/exports/`.
- Added `[export]` annotation for exporting/opening chats in the Materials panel.
- Added message-number range support such as `[export][Chat Title][4-6]`.
- Added callable export context injection when prompt text follows an export annotation.
- Updated Materials panel payloads so exported chats are the first concrete material type.
- Updated annotation suggestions so `/` and `[export]` guide Dato through export actions.

## 2026-07-02 - Export Context Accuracy Patch

- Tightened `[export]` callable context so selected exported messages are labeled as real exported chat text, not metadata.
- Added export scope lock in Core: current chat transcript/workspace context is not injected for export prompt requests.
- Added clearer structured export paths: `[export][open][Chat Title][4-6]` and `[export][use][Chat Title][4-6] prompt`.
- Kept shorthand `[export][Chat Title][4-6] prompt` working for speed.
- Improved export suggestions and help text so Dato can distinguish opening an export from using an export as prompt context.

## Patch 3 - Side Ask V1 + Simple Comments

- Added `side_ask_module` as a lightweight secondary Q&A flow.
- Added a right-panel **Side Ask** tab with Ask, Save to Chat, and New Chat actions.
- Side Ask can use selected visible chat text as temporary context.
- Side Ask answers stay out of the main transcript unless Dato explicitly saves them.
- Added `comments_module` for simple comments attached to selected chat text.
- Added an **Add Comment** button above the chat.
- Added a right-panel **Comments** tab to inspect saved comments for the current chat.
- Preserved the rule that reward/importance should be designed later as a stronger system.

## 2026-07-02 - Side Ask and Comments Polish V1.1

- Added a manual Side Ask context box separate from the question and answer boxes.
- Side Ask can now combine selected chat text and manually pasted context in one temporary context block.
- Improved Comments panel readability by showing target message numbers as `comment(number)` in the heading.
- Kept comment message detection best-effort until `[current][number]` introduces structured message references.
- Documented future visual message-number colors for comments, important, and ignore markers.
# 2026-07-27 | GUI Polish | Flow input and collapsible side panels

- **What changed:** Flow Chat now sends on Enter and inserts a newline on Shift+Enter. Chats and Flow each have a toggle arrow that hides or restores their side panel without clearing state.
- **Files/modules affected:** `amadeus_gui/flow_chat_view.py`, `amadeus_gui/main/main_window.py`, GUI tests and documentation.
- **User-visible behavior:** Faster Flow message sending and more usable conversation space when Process Monitor or workspace panels are not needed.
- **Architecture notes:** Changes remain within GUI widgets; Core, storage, LLM, and process-event ownership are unchanged.
- **Tests performed:** Focused GUI keyboard and side-panel state tests, full suite, and compilation.
- **Known limitations:** Panel visibility is retained while the application runs but is not saved between restarts.

## 2026-07-28 - Mind Map Living Interface Reconstruction

- Rebuilt the Mind Map presentation around the earlier AMADEUS relevance-graph behaviour while preserving the current SQLite/Core/service foundation.
- Added relevance-based node size, opacity, and depth; central-node gravity; typed relationship physics; directed relationship styling; and deterministic overlap separation.
- Added neighborhood focus: selecting a node keeps directly connected objects bright and fades unrelated graph content.
- Replaced the fixed CRUD-style workspace with resizable Explore, Graph, and Context panels plus Context, Details, and Connections inspection tabs.
- Added manual Chat Registry import through source upsert identity, so selected chats become stable graph nodes and repeated imports update rather than duplicate them.
- Added Core-coordinated source navigation for chat, message, sheet, and material nodes.
- Upgraded `[mindmap]` retrieval from isolated node rows to bounded node-and-link context packages containing explicit relationship direction, confidence, strength, permanence, evidence, and source references.
- Kept all graph writes behind MindMapService and Core; visual physics remains transient and never writes storage automatically.
- Validation: 15 Core/physics tests and 7 Mind Map annotation lifecycle tests passed in the headless environment; GUI sources compiled successfully. Final visual validation remains a Windows/PyQt6 runtime step.


## 2026-07-28 - Mind Map and Chat Workspace Synchronization

- Added a `MindMapWorkspaceSync` adapter between graph storage and Chat, Sheets, Comments, and Memory public APIs.
- New chats, chat-scoped sheets, comments, and explicit memory entries now gain stable source-backed graph nodes and chat relationships.
- Added real-object creation for `chat`, `sheet`, `comment`, and `memory` node types, with an explicit graph-only opt-out.
- Added default direct-neighbor prompt injection with a per-link `inject_into_chat` switch and bounded context limits.
- Added the right-panel Linked tab and automatic panel refresh after graph/workspace changes.
- Replaced relationship arrows/labels with clean straight lines and a selectable midpoint detail point.
- Fixed drag interaction so graph physics wakes during engagement and resumes after persisted movement.
- Reduced background repaint work with cached, batched grid rendering.
- Added `[mindmap]` to slash suggestions and source navigation for Sheet and Comment graph nodes.
- Added stable-id memory update/soft-delete service operations for graph/source consistency.
- Added focused cross-module synchronization tests.

## 2026-07-28 - Mind Map Interaction, Source Deletion, and Grounded Context Patch

- Fixed ordinary node selection so a click no longer starts drag physics or reflows the graph; physics wakes only after the pointer crosses a real drag threshold.
- Added a visible header-level **Edit Node** button and kept source-backed node types locked against unsafe in-place module conversion.
- Reduced drag repaint cost by temporarily disabling antialiasing and using minimal viewport updates during active movement.
- Changed Mind Map deletion so source-backed Chat, Sheet, Comment, and Memory nodes delete their real owning object by default; the confirmation dialog now warns before workspace data is removed.
- Replaced ambiguous linked-node prompt text with literal delimited Title, Type, Source, Description, Content, and Relationship fields.
- Added strict Chat grounding rules that forbid invented node labels, categories, IDs, relationships, or sheet contents and make exact graph records override older assistant guesses.
- Added guided `[mindmap]` suggestions after the annotation is selected.
- Files/modules affected: `mindmap/gui`, `mindmap/integrations`, `amadeus_core`, `amadeus_chat`, `annotation_module`, focused tests, and module documentation.
- Validation: 33 non-GUI Mind Map tests passed through a Linux compatibility runner; changed Python sources compiled successfully. PyQt interaction remains a Windows runtime validation step because PyQt6 is unavailable in this build environment.
- Known limitations: deleting a Chat node removes the chat record but does not yet cascade-delete every separate Sheet, Comment, Memory, or Material associated with that chat; no undo/archive recovery exists yet.

## 2026-07-28 - Canvas Module Workspace Foundation

- Date: 2026-07-28
- Phase: Canvas module foundation
- Feature or fix: Added the first visible AMADEUS Infinite Canvas module space.
- What changed: Added a Core-registered `CanvasModule` facade and typed workspace descriptor, a persistent Canvas navigation page, a large adaptive-grid `QGraphicsView`, drag-to-pan navigation, cursor-centred wheel zoom, lazy GUI exports, focused module tests, and Canvas documentation.
- Files/modules affected: `canvas_module`, `amadeus_core`, `amadeus_gui`, GUI and Canvas tests, root/module documentation, and this changelog.
- User-visible behavior: The main sidebar now includes Canvas. Opening it shows a real navigable workspace instead of a generic foundation-pending page.
- Architecture notes: The current phase creates only the module and GUI boundary. No Canvas objects, persistence, context injection, LLM request, or Mind Map conversion has been claimed. Future GUI actions must route through Core/module public APIs rather than owning storage or reasoning.
- Tests performed: Python compilation and focused non-GUI Canvas tests. Full Windows/PyQt6 validation remains required because this Linux environment does not provide PyQt6 or Windows-only `msvcrt`.
- Known limitations: The Canvas is empty except for navigation and visual guidance; typed blocks and structured interactions begin in the next phase.

## 2026-07-28 — Canvas semantic connectors

- Upgraded Canvas persistence to schema v2 with non-destructive loading of existing schema-v1 text-only workspaces.
- Added stable semantic connector models for plain lines and directional arrows.
- Added two-click source/target connector creation, live attached geometry, selection, labels, relation types, comments, editing, and deletion.
- Deleting blocks now atomically removes attached connectors; moving blocks preserves connector revisions and semantics.
- Added focused migration, validation, persistence, cascade-deletion, and connector-regression tests.
- Known limitations: grouping, branch traversal tools, undo/redo, viewport context, AMADEUS Canvas responses, handwriting, and images remain future work.

## 2026-07-28 — Canvas AMADEUS conversation loop

- Upgraded Canvas persistence to schema v4 with auditable send-operation history and non-destructive loading of schema-v1 through schema-v3 workspaces.
- Added an optional one-off instruction field beside `Send Changes to AMADEUS`; empty instructions use natural target-focused continuation.
- Added a Core-routed background Canvas request worker using the configured LLM client, AMADEUS identity, and shared Process Events.
- Added target-focused Canvas prompt construction that uses arrows as directional history, lines as peer context, and the viewport only as the supporting boundary.
- Successful requests now insert a movable AMADEUS response block and a persisted `responds_to` arrow from the primary target.
- The response block, connector, exact context payload, rendered prompt, optional instruction, model name, process run ID, and semantic baseline are committed atomically.
- Failed requests do not mutate the Canvas or advance the baseline; stale responses are rejected when the Canvas changes during generation.
- Added focused tests for successful commits, empty instructions, failed LLM calls, stale-response rejection, automatic baseline behavior, and schema-v3 migration.
- Known limitations: the sent baseline is currently workspace-wide rather than per branch; response-source selection for multi-target sends, retry/regenerate, groups, undo/redo, handwriting, and images remain future work.


## 2026-07-28 — Canvas fast entry, multi-target grounding, and undo

- Replaced multiline-only Canvas text dialogs with fast editors: Enter creates/saves the block and Shift+Enter inserts a line break.
- Added a visible Undo toolbar action and `Ctrl+Z` shortcut backed by complete session-local snapshot restoration.
- Undo now restores creations, edits, movement, resizing, deletion cascades, connectors, root state, semantic baselines, and AMADEUS send records atomically.
- Strengthened Canvas prompting so one generated response handles every selected or changed target instead of silently choosing one.
- Added explicit connection-flow serialization for all included arrows and lines, allowing several source blocks converging on a question to remain a combined reasoning context.
- Added comparison grounding rules that discourage unsupported shared facts and require all relevant connected source blocks to be considered.
- Added focused tests for reverse-order undo, atomic response undo, multiple targets, and multi-source connection flow.
- Known limitations: undo history resets when AMADEUS restarts; redo and multi-target response-link selection remain future work.

## 2026-07-31 — Independent module window workspace

- Changed the primary AMADEUS window into a permanent Flow Chat home instead of a stacked page container.
- Added one shared `ModuleWindowManager` and reusable top-level hosts for Chats, Code, Mind Map, Canvas, and Habit Tracker.
- Module launch buttons now open or focus the existing window, preventing duplicate GUI views and duplicate module state.
- Several module windows can remain visible simultaneously while Flow Chat stays open.
- Closing one module window preserves its view and leaves the rest of AMADEUS running; closing Flow Chat coordinates final shutdown of every module window after active requests finish.
- Existing Mind Map source navigation continues to work through a compatibility router that opens the correct independent window.
- Added focused GUI regression coverage for reusable windows, simultaneous visibility, Flow draft retention, and independent Chats/Canvas/Mind Map surfaces.
- Known limitations: module window geometry and monitor placement are not yet persisted across restarts, and intentional multi-instance windows are not yet supported.

## 2026-08-03 - Shared Creation Annotations

- Date: 2026-08-03
- Phase: Shared creation routing
- Feature or fix: Unified approval-gated chat, Sheet, and Memory creation across Flow and dedicated chat.
- What changed: Added typed `/create-chat`, `[sheet][create]`, and `[memory][save]` parsing and suggestions; bounded Inner Brain `creation_kind`; Core-owned route defaults and fixed-scope approval dispatch; dialog-only approval output; and Flow post-approval workspace refresh.
- Files/modules affected: Annotation Module, Inner Brain, Core coordinator and workspace adapter, Creation Module, Flow Chat, GUI, focused tests, module documentation, and this changelog.
- User-visible behavior: Flow creates global standalone Sheet and Memory source nodes unless `; scope: chat` is selected. Dedicated chat defaults to the active chat and linked source nodes. Creation approval is shown only in the modal dialog, followed by a local completion or decline message.
- Architecture notes: Annotation Module owns grammar and suggestions; Core owns pending actions, owner dispatch, scope, and graph synchronization. Inner Brain only advises `chat`, `sheet`, or `memory` intent and never writes data.
- Tests performed: Focused annotation, Inner Brain, pending action, Flow, Mind Map, and headless GUI tests; Python compilation and whitespace validation.
- Known limitations: Pending actions remain process-local, single-use, and expire after five minutes; creation metadata uses the existing local resolver fallback.
