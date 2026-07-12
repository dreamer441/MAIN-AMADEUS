# Memory Module Features

## Implemented

- Explicit `[memory]` annotation support.
- `[memory][global] text` saves cross-chat memory.
- `[memory][chat] text` saves memory for the active chat only.
- `[memory][list]`, `[memory][list][global]`, and `[memory][list][chat]` open memory in the right-side Memory panel.
- Global memory is injected into normal chat prompts across all chats.
- Chat memory is injected only into the active chat prompt.
- Memory is stored locally as JSONL under `data/memory/`.
- Memory entries include id, scope, timestamps, status, and source chat id.

## Design Rules

- AMADEUS does not auto-save memory in V1.
- Dato must explicitly mark memory with `[memory]`.
- Memory lists should not clutter the main chat.
- Memory is durable context, not a new user instruction.
