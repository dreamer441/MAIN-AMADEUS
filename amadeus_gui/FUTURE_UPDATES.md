# AMADEUS GUI Future Updates

- Improve chat formatting with speaker styling.
- Add manual chat rename.
- Add edit dialog for existing chat title/description.
- Add chat search and chat archive/restore.
- Add optional chat pinning, favorites, and project labels.
- Add collapsible Process Monitor panel.
- Add trace filtering by category and level.
- Add trace export for debugging.
- Add safer close/cancel behavior for long-running LLM calls.
- Keep GUI comments updated when layout or worker flow changes.

## Future GUI Panel Improvements

- Improve suggestion popup keyboard control and positioning.
- Add syntax highlighting for Code Viewer.
- Add copy button, file path copy button, and line number gutter.
- Add Diff Viewer tab before any write/edit ability is introduced.
- Add `[panel]` support later so AMADEUS can explicitly receive current right-panel context when Dato asks.

## Future Multi-Chat Improvements

- Add rename dialog for chat titles.
- Add chat creation with optional first instruction/profile.
- Add AMADEUS-generated callable chat summary when switching/closing chats.
- Add staged metadata retrieval: title first, description second, summary only when deeper context is requested.
- Add chat reason/mode only after skills and reasoning profiles define real behavior differences.
- Add per-chat module context, model preference, and reasoning profile later.
- Add pinned General Chat once project/workspace rules are clearer.
- Add side-by-side chat comparison only after basic switching remains stable.

## Memory Panel Future Updates

- Add search/filter controls for memory.
- Add delete/update buttons after Memory Module supports those actions.
- Add a “send memory to chat context” / `[panel]` bridge later.

## Current / Panel Future Updates

- Add `[current][number]` to inject one visible message by its chat-local number.
- Add `[current][start-end]` for message ranges.
- Add `[panel]` later so AMADEUS can explicitly read the current right-side panel when Dato asks.

## Side Panel GUI Growth

- [ ] Add `[panel]` annotation support once Core can request visible panel context from the GUI safely.
- [ ] Add Current Context tab.
- [ ] Add Sheets tab.
- [ ] Add Materials tab.
- [ ] Add Diff Viewer tab for future safe code patching.
- [ ] Add copy buttons and search controls to Code Viewer.

## Sheets / Materials UI Roadmap

- [x] Editable Sheets panel.
- [x] Materials panel placeholder.
- [ ] Chat export UI.
- [ ] Select exported message ranges in Materials panel.
- [ ] Text selection comments from chat messages.
- [ ] Side Ask always-open bar.

## Export GUI Future

- [ ] Add visible Export Chat button.
- [ ] Add export selector/range controls in Materials tab.
- [ ] Add Save Export Segment to Sheet action.

## Side Ask / Comments UI Future

- [ ] Add keyboard shortcut for Side Ask.
- [ ] Show selected-text preview before asking Side Ask.
- [ ] Allow saving Side Ask answers directly into sheets.
- [ ] Add visual comment markers near numbered messages.
- [ ] Add exact message selection once `[current][number]` is implemented.

## Message Metadata Visual Roadmap

- [ ] Color only the visible message number when metadata is attached.
- [ ] Use blue for comments.
- [ ] Use green for important messages.
- [ ] Use red for ignored messages.
- [ ] Avoid coloring full message text because it reduces readability.
- [ ] Add exact message-reference controls after `[current][number]` exists.
