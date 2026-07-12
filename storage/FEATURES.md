# Storage Features

## Implemented Now

- Saves user and AMADEUS messages to local JSONL files.
- Supports multiple local chats through `data/chats/chats_index.json`.
- Stores each chat in its own `data/chats/<chat_id>.jsonl` file.
- Tracks active chat id so Context Builder only receives the selected chat's history.
- Lists chats for the GUI chat selector.
- Creates new chats with safe local ids and default titles.
- Deletes chats and automatically keeps/creates a valid active chat.
- Migrates older `data/chats/current_chat.jsonl` history into the new `main` chat when needed.
- Loads recent messages when the GUI starts or when the user switches chats.
- Keeps chat files out of git through `.gitignore`.
- Contains comments explaining visible chat persistence, per-chat files, active chat selection, and why this is not long-term memory yet.

## Boundaries

- Storage is still visible chat history only.
- Storage does not manage semantic memory, mind map data, autonomous reflection, or file edits.
- Storage should not decide what context belongs in the LLM prompt; Context Builder uses Storage for that.


## Chat Workspace Metadata V2

- Chat metadata now supports title, description, and a reserved summary field.
- New chats can be created with title and description.
- Existing chat indexes without description/summary are still accepted for backward compatibility.
- Loaded messages include a computed chat-local `message_number` based on JSONL row order.
- Message numbers are visible/UI references now and prepare future `[current][number]` retrieval.
