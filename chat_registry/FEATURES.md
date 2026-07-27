# Chat Registry Features

## Implemented Now

- Returns immutable metadata records containing only `chat_id`, `title`, `description`, `priority`, `purpose`, and `scope`.
- Reads existing dedicated-chat metadata through `ChatHistoryStore`.
- Provides list, ID lookup, and a future-ready relevant-metadata method.
- Does not create a second chat database.
- Does not load dedicated-chat messages or expose message bodies.
- Treats scope as descriptive V1 metadata only; it performs no retrieval policy.
