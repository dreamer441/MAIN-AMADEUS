# Flow Chat Features

## Implemented Now

- Persistent Flow home conversation, separate from dedicated chats.
- Local Flow JSONL storage at `data/flow_chat/flow_messages.jsonl`.
- Atomic persistence of successful user/AMADEUS exchanges; failed requests do not save a partial exchange.
- Corruption-tolerant history loading that skips malformed local rows.
- Layer 0 context: bounded, chronological recent Flow history.
- Layer 1 context: current dedicated-chat registry metadata formatted separately from Flow history.
- Metadata-only registry records with `chat_id`, title, description, priority, purpose, and scope; no dedicated-chat message bodies are read or exposed.
- Scope is descriptive in V1 only and never causes automatic cross-chat retrieval.
- Registry reads the live dedicated-chat list for each Flow context build, reflecting create, metadata-update, and delete mutations.
- Shared Chat module, identity prompt builder, and safe Process Monitor lifecycle through the separate Core Flow route.
- Live shared event delivery and final event-payload reconciliation for the GUI.
- Flow declares its route work plan, reports actual Flow-history loading and
  metadata-only registry loading, then records configured-LLM response composition
  and successful isolated exchange storage without exposing prompt or chat bodies.
- [x] Explicit read-only `/review <question>` context: reads the Changelog and
  Future Implementations first, then current Git state and a bounded set of safe
  changed project files; ignored/runtime paths and unsafe files are omitted.
- [x] Explicit `/create-chat <request>` returns a Core-owned approval request for a dedicated editable chat.
  Recognized Title, Description, Weight, and Priority fields override strict local
  Ollama JSON metadata; unavailable or invalid generation uses New Chat, an empty
   description, and Normal priority.
- [x] Shared creation uses `/create-chat`, `[sheet][create]`, and `[memory][save]`; legacy `/create-sheet` and `/create-memory` are not creation commands.
- Flow typing `/` uses the same annotation popup as dedicated chat. Arrow keys select, Enter/Tab insert, Escape hides, and Enter sends when the popup is closed.
- Approved records are projected through Core-owned Mind Map workspace synchronization. Dedicated-chat prompt context includes only direct linked neighbors; global records are not linked to a chat.
- Flow Sheet and Memory creation defaults to global scope with no linked chat or graph relationship. `; scope: chat` explicitly links the current chat.
- Plain Flow messages receive only Core-resolved safe no-argument inferred read context. Inner Brain may advisory-detect only chat, sheet, or memory creation; Core still requires GUI approval.
- [x] `/habit` provides deterministic local reads and approval-gated writes for every
   Habit Tracker action: one-time tasks, routines, calendar events, Eisenhower
   tasks, timers, and alarms. Supported natural aliases remain bounded to Habit
   Tracker vocabulary; ambiguous dates/times return guidance instead of guessing.
- [x] Natural one-time task creation defaults to today when no date is supplied;
   supported natural dates are extracted before optional task fields. Eisenhower task
   labels are not included in the stored task title.
- [x] A dedicated Flow Habit request boundary consumes raw text before other Flow
  routes. It returns typed local reads, validated approval requests, or specific
  validation guidance, so Habit parser failures never become generic Flow failures.

## Core ownership cleanup — 2026-09-12

- Implemented: FlowRequestHandler owns command routing, approval preparation, annotation delivery, safe errors and isolated exchange persistence. Core forwards the request. Shared chat-creation metadata has a compatibility export to Creation.
