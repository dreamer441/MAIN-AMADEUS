# Phase 6 Comments And Export Display Cleanup Design

## Scope

Phase 6 improves the Comments and Materials side panels without changing their
ownership boundaries. Comments remain owned by `comments_module`; exported chat
records remain owned by `export_module` and are exposed through
`materials_module`.

## Comments

The existing `Add Comment` control becomes context-sensitive. When visible chat
text is selected, it creates a selection comment. When no text is selected, it
creates a general chat comment. Both flows use the same comment-input dialog.

`CommentEntry` will retain the following fields in JSON storage:

- `comment_id`
- `chat_id`
- `message_number`, when detected
- `selected_text`, when selected
- `comment`
- `created_at`
- `comment_type`, either `selection` or `general`
- `updated_at`, when edited

Older records without `comment_type` will be read as selection comments when
they contain selected text, otherwise as general comments. This keeps existing
runtime comment records usable without rewriting them.

The comment store and service will add edit, delete, and lookup operations. The
GUI will keep display state only: it asks Core for the current chat's payload and
passes explicit user actions to Core. Comment records are never edited directly
by the GUI.

The Comments tab will use a selector with action buttons, matching the existing
Materials-panel interaction model:

- Edit opens the existing multiline dialog with the saved comment text.
- Delete removes the selected comment after an explicit confirmation.
- Jump to Message scrolls the visible chat history to the matching numbered
  message when `message_number` exists; it is disabled for general comments and
  selection comments whose source number could not be detected.
- Refresh reloads the current chat's comment payload.

The readable panel display deliberately omits comment IDs and timestamps. A
selection comment renders as `Comment(12) - text` followed by `Selection: text`.
A general comment renders as `Comment(A) - text` with no selection line.

## Exports

Export files and index records keep their detailed metadata, including IDs,
paths, and timestamps. The Materials panel's export list presents only useful
scan information:

- Export name
- A human-readable export date, such as `13 July 2026`
- `Messages first-last` when the exported message bounds are available, otherwise
  `Messages count`

Export records will carry optional first and last message numbers so the panel
does not need to parse export files while rendering the list. Older index rows
without those bounds fall back to the stored message count. Re-exporting updates
the bounds together with all other metadata.

For an export selected in Materials, the buttons are labelled Open, Use in Next
Message, Copy Path, Delete, and Refresh. Copy Path copies the export's TXT path;
the path remains available internally in metadata but does not appear in the
row. Existing non-export managed-material actions keep their present behavior.

## Error Handling

Empty comments are rejected by the store. Unknown comment IDs and export IDs
produce existing GUI status errors without mutating storage. A missing or
unparseable message number prevents jumping rather than guessing a position.
Invalid export timestamps and older export records use safe display fallbacks.

## Validation

Focused tests will cover comment creation with and without selections, edit and
delete persistence, clean panel payload formatting, export date/range display,
and old-record fallback behavior. The complete repository Python compilation
check and relevant test suite will run before implementation is committed.
