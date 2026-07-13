# AMADEUS Global Changelog

Append-only global project progress log. Module-specific details still belong in each module's `FEATURES.md` and `FUTURE_UPDATES.md`.

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
