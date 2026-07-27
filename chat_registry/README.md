# Chat Registry

The Chat Registry exposes a small, read-only view of dedicated-chat metadata.

It wraps `ChatHistoryStore` and returns only a chat ID, title, and description.
It never loads or returns dedicated-chat message history. Flow Chat uses this
metadata to know which dedicated workspaces exist without claiming knowledge of
their contents.

Registry results are read from the existing chat store for each request, so
dedicated-chat creation, metadata updates, and deletion are visible immediately.
