# AMADEUS Global Changelog

Append-only global project progress log. Module-specific details still belong in each module's `FEATURES.md` and `FUTURE_UPDATES.md`.

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
