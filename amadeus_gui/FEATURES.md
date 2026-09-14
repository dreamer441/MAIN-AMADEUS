# AMADEUS GUI Features

## Implemented Now

- PyQt6 desktop window.
- Chat history display.
- Message input and Send button.
- Background response worker so local LLM calls do not freeze the GUI.
- Startup loading of persisted chat history.
- Top chat selector for switching between local chats.
- `New Chat` button for creating a fresh chat.
- `Delete Chat` button with confirmation before removing the selected local chat history.
- Chat switching reloads the selected chat's saved history and clears right-panel state.
- Chat controls are disabled while AMADEUS is answering so responses are not saved into the wrong chat.
- Process Monitor panel showing the latest message execution trace.
- Compact/Detailed trace display mode selector.
- GUI response handling supports Core's dictionary payload: response text, compact trace, detailed trace, structured trace events, and side-panel data.
- Flow and dedicated Chats handle `approval_request` payloads with the same modal Approve / Decline dialog after the response worker returns to the GUI thread.
- Approval requests do not add transcript approval text. The dialog is the only confirmation surface; completion or decline is appended after it closes.
- Contains comments explaining GUI/Core separation, worker threading, trace display, response payload handling, and multi-chat UI safety.

## Flow Chat Navigation Shell

- `AmadeusMainWindow` is the permanent Flow Chat home window and opens with Flow ready at startup.
- Flow Chat keeps its own persistent history, Core-owned Flow request route, background worker, live Process Monitor, and safe busy/error recovery.
- The existing dedicated-chat surface opens in its own reusable top-level `Chats` window, including chat management, annotations, and the full right-side workspace.
- Code and Habit Tracker open as independent reusable windows that retain their widget state while hidden or reopened.
- The GUI receives Flow history through Core and never reads Flow storage directly.
- Flow renders shared Process Monitor events as they arrive and replaces that provisional view with Core's completed event payload.
- After Flow approval, global workspace panels and the Mind Map refresh without selecting or opening a dedicated chat.
- Mind Map opens as a persistent Core-backed graph window with an interactive layout canvas. Habit Tracker is a local task-planning workspace; Code remains a named placeholder window.
- Canvas opens as a persistent Core-backed spatial conversation window with typed movable blocks, semantic lines/arrows, root and context controls, an optional instruction field, background AMADEUS sending, and movable AMADEUS response blocks.

## Independent Module Windows

- Flow Chat remains mounted in the primary AMADEUS window and never disappears when another module opens.
- Chats, Code, Mind Map, Canvas, and Habit Tracker each open in their own top-level window.
- Several module windows can stay open at the same time for parallel work.
- Reopening an already-created module raises and focuses the existing window instead of constructing a duplicate view or duplicate module state.
- Closing one module window does not close Flow Chat or the other modules.
- Closing the Flow Chat main window coordinates final shutdown and closes every module window after active workers finish.
- The `ModuleWindowManager` owns only GUI window lifecycle; all windows continue using the same Core and module instances.

The Process Monitor shows real events such as input received, annotation check, routing decision, chat module use, LLM call status, errors, and output ready.

## Multiline Input and Right Panel v1

- Chat input is multiline.
- Enter sends the message; Shift+Enter creates a new line.
- Typing `/` opens a simple annotation suggestion list above the input.
- Right panel uses tabs: Process Monitor and Code Viewer.
- Code Viewer displays exact read-only file content returned by `[file][module][file.py]`.
- Main chat stays clean by receiving only a short “opened in Code Viewer” response for file-content commands.

## Multi-Chat v1

- The top selector lists local chats from Storage.
- Switching chats updates the active Storage chat used by Core and Context Builder.
- Creating a chat switches to a blank new conversation immediately.
- Deleting a chat removes its local JSONL file; if it was the last chat, Storage creates a fresh `Main Chat`.

## Right Panel Memory Tab

- Added a Memory tab beside Process Monitor and Code Viewer.
- `[memory][list]` opens saved memory in the right panel instead of dumping it into chat.
- Memory panel shows scope, global memory count, chat memory count, and explicit memory entries.


## Chat Workspace V2

- Main chat messages are visibly numbered as `[1]`, `[2]`, `[3]`, and so on.
- Message numbers are chat-local and are reconstructed from stored JSONL order when a chat loads.
- `New Chat` now opens a dialog with title and optional description.
- `New Chat` and `Edit Chat` collect title, description, priority, purpose, and scope; Edit Chat preserves the active transcript and UI state.
- Dedicated Chats expose a compact response-length selector beneath Send with None, Short, Normal, Large, and Full Send titles; it persists to the active chat immediately.
- NONE response payloads retain the user message and Process Monitor lifecycle but do not add an AMADEUS transcript bubble.
- Chat controls, including Edit Chat, remain disabled while AMADEUS is answering.
- Chat description is shown in the right-side Memory panel as current chat context.
- Memory panel now combines current chat context with explicit memory lists when `[memory][list]` is used.
- Contains comments explaining why message numbers support future `[current]` annotations and why chat descriptions are active chat context, not global memory.

## Side Panel Foundation

- Extracted the right-side Process Monitor / Code Viewer / Memory tab rendering into `amadeus_gui/right_panel_widget.py`.
- `main_window.py` now delegates panel rendering instead of owning every panel widget directly.
- The GUI right panel uses the new `side_panel` payload/state module as its logic foundation.
- Current behavior is preserved: Core can still return `side_panel` payloads for code and memory, and the GUI displays them in the correct tab.
- Added comments explaining that the right panel displays content from other modules but does not own file reading, memory storage, or trace creation.

## Sheets and Materials UI

- Added `Sheets` tab to the right panel.
- Sheets can be created, edited, saved, and deleted directly from the side panel.
- Sheets support `chat` and `global` scope.
- Added `Materials` tab foundation for future exports and uploaded references.

## Export Display

- Materials tab can now show exported chat lists and selected numbered ranges returned by Core.
- No large export text is dumped into the main chat unless Dato explicitly saves/asks later.

## Phase 5 Materials Controls

- Materials lists managed files and export records supplied by Core with id/type/metadata details.
- Preview and Open are display-only. Use in Next Message is consumed by the next send only; Ask AMADEUS uses the selected reference explicitly.
- Copy Ref receives a Core-provided stable reference. Remove asks for confirmation, and Refresh reloads Core's payload.

## Side Ask / Comments UI

- Right panel includes a Side Ask tab.
- Side Ask can ask a question without saving into the main chat.
- Side Ask can save its Q&A to the current chat.
- Side Ask can create a new chat from its Q&A.
- Added Add Comment button for selected chat text.
- Right panel includes a Comments tab for current-chat comments.

## Chat Data

- Dedicated Chats include a Chat Data tab, separate from Materials.
- Analyze / Refresh explicitly generates title/description candidates, short bullets, detailed summary, and model metadata; it does not run on panel refresh.
- Create Export explicitly uses the existing chat export service and records only the export reference.
- Suggested inferred writes are shown as non-executable information.

## Phase 6 Comment Follow-Up

- General comments display as `Comment(A)`; selected text without a detected message displays as `Comment(?)`, retains Selection details, and cannot jump.
- Comment jumps match only the start of a rendered numbered-message block, not matching text inside message content.

## Side Ask and Comments Polish V1.1

- Side Ask tab now has three separate areas: question, optional context box, and answer.
- The optional context box lets Dato paste a message/code snippet without relying only on chat text selection.
- MainWindow combines selected chat text and manual Side Ask context before sending the Side Ask request to Core.
- Comments panel headings now show `comment(message_number)` for easier reading and future metadata linking.

## Phase 2 GUI Package Boundary

- `amadeus_gui.main` owns the main window and whole-window chat coordination.
- `amadeus_gui.side` owns the tabbed right-side workspace panel and its Qt rendering.
- `amadeus_gui` keeps `AmadeusMainWindow` as the stable public GUI import used by application startup.
- No visible layout, controls, or panel behavior changed during the package move.

## Phase 3 Annotation Suggestions

## Code Viewer Browser Polish

- The project browser is collapsed by default and can be expanded from the `Project Browser` dropdown control.
- File and folder names are shown without text elision; a horizontal scrollbar preserves complete long paths.

- The visible annotation suggestion list supports Up/Down selection, Enter or Tab insertion, and Escape to hide it.
- When the suggestion list is closed, the input keeps its normal Enter-send and Shift+Enter-newline behavior.

## Phase 4 Code Viewer Navigation

- Code Viewer now displays a Core-provided project tree with lazy expand/collapse, refresh, root-relative path display, and filename filtering.
- Double-clicking a tree file opens verified content; Copy Relative Path copies only the selected verified path.
- Displayed code has one-based line labels, including blank source lines.
- Ask AMADEUS About File has an explicit, default-off Include code context control and optional `15` or `15-30` line selector.
- With context disabled, the visible file remains visual only; with context enabled, only the verified selected file/range enters that direct Ask request.

## Chat Interaction Polish

- Flow Chat now uses Enter to send and Shift+Enter to insert a new line, matching dedicated Chats.
- Flow Chat and Chats each have an arrow control that hides or restores their side panel without clearing its state.
- Flow Chat and dedicated Chats keep their original left-aligned transcript style with two blank rows between messages for readability.
- User and AMADEUS transcript headings are bold while the message body remains normal weight.

## Live Process Monitor Coverage

- Material-backed chat requests now forward the existing safe Process Monitor events live, matching normal chat requests.

## Mind Map Page

- The Mind Map module uses one persistent `MindMapView` hosted by its independent reusable top-level window.
- The view receives snapshots and graph-change subscriptions through Core only, then renders its SQLite-backed nodes and links on a zoomable `QGraphicsView` canvas.
- Node/link CRUD, drag position persistence, search, layout, and JSON import/export remain module-owned operations invoked through Core wrappers.

## Linked Mind Map chat context

- The Chats right panel includes a Linked tab showing direct graph neighbors and whether each relationship enters prompt context.
- Source-backed Sheet and Comment nodes open their owning chat/panel.
- Mind Map links render as straight lines with a midpoint detail control, and dragging wakes/resumes graph physics.

## Canvas Workspaces

- Canvas now exposes a lightweight workspace selector with New, Rename, and Delete controls.
- Switching workspaces re-renders one independent persisted Canvas document without mixing roots, baselines, send history, connectors, or undo state.
- Workspace deletion is confirmed in the GUI and archives the document instead of permanently deleting it.
- Workspace controls are disabled while a Canvas LLM request is active, preventing a response from being committed into the wrong project.

## Habit Tracker

- Habit Tracker is now a reusable local workspace instead of a placeholder.
- It provides routines, one-time tasks, calendar events, Eisenhower tasks, timers, and due-alarm notifications through its own local SQLite service.
- The port intentionally excludes the standalone task manager's embedded AMADEUS chat UI; Flow Chat remains the one AMADEUS conversation surface.

## Module Metadata Display

- `[metadata]` results open in the existing Memory tab as labelled verified `FEATURES.md` and/or `FUTURE_UPDATES.md` content.
- Metadata display omits the normal current-chat memory prefix so the fixed-file source text remains exact.

## Core ownership cleanup — 2026-09-12

- Implemented: Canvas and Habit Tracker operations use Core routes. MainWindow injects the shared Habit facade, avoiding a second independent application service.
