# Storage

Storage keeps local AMADEUS runtime data.

Chat history is stored per workspace under `data/chats/<chat_id>.jsonl`; the
existing `data/chats/chats_index.json` stores active-chat and validated metadata.
Each chat has title, description, priority, purpose, and scope. Priority defaults
to Normal, purpose to General, and scope to Local; legacy rows safely receive
those defaults. Scope is descriptive metadata, not retrieval permission.

It is not long-term memory yet. It only lets the GUI resume recent conversation messages.
