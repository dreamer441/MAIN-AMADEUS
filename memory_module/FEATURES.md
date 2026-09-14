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
- Structured SQLite memory foundation at `data/memory/memory.sqlite` mirrors legacy explicit JSONL entries without replacing JSONL reads.
- Structured Memory Bricks support multiple domains, kinds, and categories plus scope, evidence, importance, confidence, and safe legacy metadata.
- Source registration stores locators only and creates five pending knowledge-layer placeholders: metadata, summary, entities, relationships, and retrieval.
- Structured memory search supports scope/label filters and SQLite FTS with a parameterized `LIKE` fallback. A null vector-store adapter preserves a future local-index boundary.
- Source hashes mark derived knowledge layers stale; no layer generation or autonomous memory creation runs in this foundation.
- Registered knowledge sources can safely retain caller-supplied raw content without resolving arbitrary locators. Creation Module V1 uses that explicit content to generate protected metadata, categorization, and temporary memory proposals.
- Approved Creation proposals write through the existing JSONL-compatible Memory Service and structured SQLite Memory Brick storage using stable source-derived IDs. Proposals never persist before explicit approval.

## Design Rules

- AMADEUS does not auto-save memory in V1.
- Dato must explicitly mark memory with `[memory]`.
- Memory lists should not clutter the main chat.
- Memory is durable context, not a new user instruction.

## Mind Map projection

- Explicit memory saved through `[memory]` can be projected into a source-backed Mind Map node and linked to its source chat.
- Memory service/store now expose stable-id lookup, update, and soft-delete operations so source-backed graph edits can remain consistent.
- `memory_module.mindmap_projection.memory_brick_projection()` produces source-backed Memory Brick metadata compatible with the existing Mind Map service boundary.
