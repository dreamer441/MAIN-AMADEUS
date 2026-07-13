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
- Contains comments explaining GUI/Core separation, worker threading, trace display, response payload handling, and multi-chat UI safety.

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

## Side Ask / Comments UI

- Right panel includes a Side Ask tab.
- Side Ask can ask a question without saving into the main chat.
- Side Ask can save its Q&A to the current chat.
- Side Ask can create a new chat from its Q&A.
- Added Add Comment button for selected chat text.
- Right panel includes a Comments tab for current-chat comments.

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
- Use in Next Message and Ask AMADEUS About File emit GUI signals to MainWindow, which delegates to Core only.
- Selected-file context is explicit and one-shot; browsing or opening a file alone never adds it to chat context.
