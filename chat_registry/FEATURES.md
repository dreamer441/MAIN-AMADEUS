# Chat Registry Features

## Implemented Now

- Returns immutable metadata records containing only `chat_id`, `title`, and `description`.
- Reads existing dedicated-chat metadata through `ChatHistoryStore`.
- Provides list, ID lookup, and a future-ready relevant-metadata method.
- Does not create a second chat database.
- Does not load dedicated-chat messages or expose message bodies.
