# Storage Future Updates

- Add manual chat rename from the GUI.
- Add chat search.
- Add chat export/import tools.
- Add schema/version fields for stored chat rows and chat index rows.
- Add tests for corrupted JSONL lines, corrupted index files, deleted chat files, and empty messages.
- Add archive/restore instead of permanent delete.
- Add separate storage areas for short-term visible chat, long-term memory, panel snapshots, and project artifacts.
- Add `[current]` and future `[panel]` references that can store/reuse selected chat or side-panel context safely.
- Separate chat history from future AMADEUS memory so old conversations do not become uncontrolled identity/memory context.


## Callable Chat Metadata Future Updates

- Generate/update chat summaries when switching chats, closing chats, or manually requesting a summary.
- Treat generated chat summaries as callable context, not always-active memory.
- Support staged retrieval: title -> description -> summary only when needed.
- Add stable message IDs later if `[current]` needs stronger references than chat-local row numbers.
