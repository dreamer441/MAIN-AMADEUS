# AMADEUS Future Implementations

Global checklist for project-wide tracking. Do not delete completed items; check them off and keep adding future work. Module-specific plans still belong in each module's `FUTURE_UPDATES.md`.

## Foundation
- [x] Clean modular shell
- [x] Identity Module
- [x] Process Monitor
- [x] Documentation/comment workflow rules
- [x] Normal-chat vs exact-file annotation separation
- [x] Right-side Code Viewer
- [x] Multi-chat V1
- [x] Memory V1
- [x] Chat Workspace V2 message numbering and title/description

## Chat Workspace
- [x] Visible message numbers
- [x] New chat dialog with title and description
- [x] Current chat context shown in Memory panel
- [ ] Edit/rename existing chat title and description
- [ ] Pinned General Chat
- [ ] Archive/restore chats instead of only delete
- [ ] AMADEUS-generated callable chat summaries
- [ ] Staged chat retrieval: title -> description -> summary
- [ ] Chat reason/mode system with real behavior differences

## Annotations
- [x] `[file]` exact file access
- [x] `[identity]` inspection
- [x] `[memory][global]` and `[memory][chat]`
- [ ] `[current][number]` message context injection
- [ ] `[current][start-end]` message range injection
- [ ] `[panel]` right-panel context injection
- [ ] Better keyboard navigation for annotation suggestions

## Memory and Retrieval
- [x] Explicit active global/chat memory
- [ ] Separate callable memory/context storage for file reads, chat summaries, and panel snapshots
- [ ] Memory update/delete commands
- [ ] Importance levels
- [ ] Conflict detection and memory aging

## Code Workspace
- [x] Read-only Code Viewer
- [ ] Line numbers
- [ ] Copy button
- [ ] Search inside opened file
- [ ] Diff Viewer
- [ ] Permission-based file patching only after read-only flow is stable

## Reasoning / Skills / Autonomy
- [ ] Reasoning profiles
- [ ] Skills registry
- [ ] Task module
- [ ] Mind map / relevance graph integration
- [ ] PermissionGuard and reversible actions
- [ ] Logged autonomy after safe read-only and draft stages

## Side Panel Workspace
- [x] Dedicated `side_panel` module for payload/state structure
- [x] Reusable GUI right-panel widget
- [ ] `[panel]` annotation that injects current visible panel context
- [ ] Current Context tab showing what AMADEUS can see
- [ ] Sheets tab
- [ ] Materials tab
- [ ] Diff Viewer tab
- [ ] Panel snapshot storage as callable memory


## Sheets / Materials / Export

- [x] Add `sheets_module` with local JSON storage
- [x] Add editable Sheets tab in the right-side panel
- [x] Add global/chat-scoped sheets
- [x] Add `[sheet]` annotation foundation
- [x] Add `[sheet][scope][title] prompt` callable sheet context injection
- [x] Add `materials_module` foundation
- [x] Add Materials tab placeholder
- [x] Add chat export as TXT, MD, and JSON
- [x] Add `[export][chat name]` annotation
- [x] Add `[export][chat name][4-6]` segment injection using message numbers
- [x] Display exported chats in Materials panel
- [ ] Add uploaded text/Markdown materials
- [ ] Add PDF materials
- [ ] Add image materials later

## Chat Export / Materials

- [x] Add `export_module` for chat export records.
- [x] Export chats as TXT, Markdown, and JSON.
- [x] Show exported chats in the Materials panel.
- [x] Support `[export][chat title][4-6]` message-range references.
- [x] Support callable export context injection for selected ranges.
- [x] Add strict export scope lock so `[export][chat][range] prompt` does not answer from the current chat transcript.
- [x] Label selected export ranges as real exported chat text, not metadata.
- [x] Add clearer structured paths: `[export][open]` and `[export][use]`.
- [ ] Add clickable export/range picker in Materials panel.
- [ ] Add export segment selector that builds `[export][use][chat][range]` automatically.
- [ ] Add GUI export button near the chat selector.
- [ ] Add export delete/archive controls in Materials panel.
- [ ] Add export summaries and staged export retrieval.
- [ ] Allow Mind Map nodes to link to export ranges as evidence.

## Side Ask / Comments

- [x] Side Ask right-panel tab.
- [x] Optional selected-text context for Side Ask.
- [x] Save Side Ask Q&A to current chat.
- [x] Create new chat from Side Ask Q&A.
- [x] Simple selected-text comments.
- [ ] Side Ask branch links between original chat and new chat.
- [ ] Save Side Ask result directly to sheets.
- [ ] Promote Side Ask result to memory after confirmation.
- [ ] Structured comments on exact message ids after `[current][number]` exists.
- [ ] Comments on sheets, materials, nodes, and links.
- [ ] Reward/importance system after comments are stable.

## Message Metadata / Visual Markers

- [x] Display comment target message number in the Comments panel as `comment(number)`.
- [ ] Add exact structured message references for comments after `[current][number]` exists.
- [ ] Add colored message-number badges when messages have attached metadata.
- [ ] Use blue message-number badge for comments.
- [ ] Use green message-number badge for important messages.
- [ ] Use red message-number badge for ignored messages.
- [ ] Keep message text itself uncolored so readability stays high.
