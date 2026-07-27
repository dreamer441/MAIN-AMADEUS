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

- Chat metadata supports title, description, reserved summary, priority, purpose, and scope fields.
- Priority is validated as Critical, Important, Normal, Low, or Ignore; purpose as General, Project, Study, Development, or Other; scope as Local, Project, or Global.
- New chats default to Normal/General/Local and can set all metadata fields during creation or editing.
- Existing chat indexes without the V2 fields, or with invalid legacy values, safely load with those defaults.
- Loaded messages include a computed chat-local `message_number` based on JSONL row order.
- Message numbers are visible/UI references now and prepare future `[current][number]` retrieval.
