# AMADEUS Future Implementations

Global checklist for project-wide tracking. Do not delete completed items; check them off and keep adding future work. Module-specific plans still belong in each module's `FUTURE_UPDATES.md`.

- [x] Add Flow Inner Brain advisory inference only with the same explicit-command precedence and safe read-context validation used by dedicated Chats.
- [x] Require Core-owned visible approval for inferred and explicit Flow creation actions; retain only bounded process-local pending records.

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
- [ ] Second Brain action detection and command routing, including intent-to-`/review` routing without embedding keyword heuristics in Flow Chat
- [ ] Second Brain intent-to-`/create-chat` routing without embedding natural-language detection in Flow Chat

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

## Mind Map Intelligence / Graph Curator

- [x] Preserve deterministic SQLite/Core graph authority while reconstructing the living relevance interface.
- [x] Add manual source-backed Chat Registry import and two-way source navigation.
- [x] Expand `[mindmap]` retrieval through explicit graph neighborhoods and relationship evidence.
- [ ] Add a Graph Curator submodule with its own specialized LLM prompt and model route.
- [ ] Add structured chat analysis for summary, ideas, decisions, tasks, requirements, risks, open questions, and evidence.
- [ ] Add graph-change proposals and validation before any LLM-created node/link mutation.
- [ ] Add manual curator invocation before Creation Mode, Drift Mode, or Chat-model-triggered invocation.
- [ ] Add proposal review for merges, major importance changes, contradictions, and destructive actions.
- [ ] Add semantic duplicate detection, cluster summaries, and knowledge-gap proposals.


## Mind Map ↔ Workspace synchronization follow-ups (2026-07-28)

- Add a real Materials creation API before `material` nodes can create and synchronize actual Materials records.
- Add retroactive per-chat import for existing sheets, comments, memories, materials, and selected message ranges.
- Add token-aware prioritization and per-node injection controls when a chat has many direct graph neighbors.
- Add a reviewable Graph Curator proposal layer for structured extraction, relationship discovery, duplicate handling, and metadata generation.
- Keep default chat context limited to explicit direct links; add deep/cluster retrieval as separate intentional operations.
- Add recovery/compensation for multi-module writes and conflict handling for simultaneous source/graph edits.

## Infinite Canvas / Spatial Conversation

- [x] Add a first-class Core-registered Canvas module and visible zoomable/pannable workspace shell.
- [x] Add typed text blocks with stable IDs and direct editing.
- [x] Add selection, multi-selection, dragging, and deletion.
- [ ] Add resizing, copy/paste, undo, redo, layering, and locking controls.
- [x] Add semantic lines/arrows, relationship labels, connector comments, and attached movement.
- [ ] Add groups, branch traversal, relation filtering, and branch highlighting.
- [x] Add safe structured Canvas persistence with document/object/connector revisions and schema migration.
- [ ] Use the visible viewport as the default context lens, with explicit selection, branch, and whole-canvas modes.
- [ ] Add context preview, token budgeting, and honest excluded-object reporting.
- [ ] Send structured Canvas context to AMADEUS and insert movable source-linked response blocks.
- [ ] Add delta-based repeated sends using object and connector revisions.
- [ ] Convert reviewed Canvas branches into Mind Map candidates through the Creation Module.
- [ ] Add stylus strokes, handwriting recognition, graph interpretation, imported images, and later visual collaboration.

## Ownership cleanup completed — 2026-09-14

Core now routes to owner workflows; application composition and workspace integration have dedicated homes. Follow-up work should add narrow service protocols, retire compatibility imports after migration, and define general skill/capability permissions without moving execution back into Core. Reasoning and Skills remain placeholders.
