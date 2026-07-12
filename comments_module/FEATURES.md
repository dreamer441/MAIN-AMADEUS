# Comments Module Features

- Stores comments in `data/comments/comments.json`.
- Supports comments attached to the current chat.
- Captures selected chat text when available.
- Best-effort extraction of visible message numbers from selected text like `[4] User: ...`.
- Provides a Comments side-panel payload.

## Comments Polish V1.1

- Comments panel now shows target message number in the heading format `comment(number)`.
- Comments still store the full selected text preview and internal comment id.
- Unknown targets are shown as `comment(?)` instead of pretending the message number is known.
