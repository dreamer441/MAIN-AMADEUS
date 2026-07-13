# AMADEUS Global Changelog

Append-only global project progress log. Module-specific details still belong in each module's `FEATURES.md` and `FUTURE_UPDATES.md`.

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
