# Side Panel Future Updates

- [ ] Add `[panel]` annotation to inject current visible panel context into the next LLM prompt.
- [ ] Add a Current Context tab showing exactly what AMADEUS can currently see.
- [ ] Add Sheets tab when the sheets module returns panel payloads.
- [ ] Add Materials tab when material previews are implemented.
- [ ] Add Diff Viewer tab for future safe code-editing workflows.
- [ ] Add copy/export actions for Code Viewer and Memory panel.
- [ ] Add optional panel snapshot storage as callable memory, not active always-on memory.
- [ ] Add keyboard shortcuts for switching panel tabs.

## Future Side Panel Tabs / Context

- [x] Add Sheets tab.
- [x] Add Materials tab foundation.
- [ ] Add `[panel]` context injection for visible tab contents.
- [ ] Add Diff Viewer tab.
- [ ] Add Materials list with exported chats and uploaded files.
- [ ] Add comments panel for selected messages/materials/sheets.

## Materials / Export Panel Future

- [ ] Add clickable export selector instead of plain text list.
- [ ] Add range picker for exported message numbers.
- [ ] Add `Open in Context` action for selected export ranges.

## Materials / Export Panel Future Work

- [ ] Add clickable export list rows.
- [ ] Add message-range selector for exports.
- [ ] Add an "Inject selected range" action that builds `[export][use][chat][range]` automatically.

## Side Ask / Comments Panel Future

- [ ] Side Ask selected-context preview.
- [ ] Comment search/filter panel.
- [ ] Panel context support for `[panel][sideask]` and `[panel][comments]`.

## Message Metadata Panel Future

- [ ] Show comment markers next to exact message references after structured message ids exist.
- [ ] Add filter/search for comments by target message number.
- [ ] Add message-number color badges in the main chat once importance/ignore metadata is implemented.
