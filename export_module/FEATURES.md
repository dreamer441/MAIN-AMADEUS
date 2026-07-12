# Export Module Features

- Exports chats to TXT, Markdown, and JSON under `data/exports/`.
- Keeps an `exports_index.json` so exported chats are listable and callable.
- Uses visible chat message numbers in all export formats.
- Supports Materials panel display for exported chat lists and selected ranges.
- Supports callable export context for specific message ranges through `[export][chat][4-6] prompt`.
- Re-exporting the same chat updates the same export record instead of creating stale duplicates.
- Labels selected ranges as **real exported chat text**, not metadata.
- Provides a strict prompt-context contract for exported ranges so AMADEUS should not answer from the wrong/current chat.

## Annotation Commands

Preferred structure:

- `[export]` exports/opens the current chat.
- `[export][list]` opens the export list in Materials.
- `[export][help]` shows usage help.
- `[export][open][Chat Title]` exports/opens a named chat.
- `[export][open][Chat Title][4-6]` opens an exact numbered message segment in Materials.
- `[export][use][Chat Title][4-6] prompt` injects only that segment as callable context.

Backward-compatible shorthand:

- `[export][Chat Title]` exports/opens a named chat.
- `[export][Chat Title][4-6]` opens an exact numbered message segment.
- `[export][Chat Title][4-6] prompt` injects only that segment as callable context.
