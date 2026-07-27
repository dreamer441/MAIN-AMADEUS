# Flow Chat Features

## Implemented Now

- Persistent Flow home conversation, separate from dedicated chats.
- Local Flow JSONL storage at `data/flow_chat/flow_messages.jsonl`.
- Atomic persistence of successful user/AMADEUS exchanges; failed requests do not save a partial exchange.
- Corruption-tolerant history loading that skips malformed local rows.
- Layer 0 context: bounded, chronological recent Flow history.
- Layer 1 context: current dedicated-chat registry metadata formatted separately from Flow history.
- Metadata-only registry records with `chat_id`, title, and description; no dedicated-chat message bodies are read or exposed.
- Registry reads the live dedicated-chat list for each Flow context build, reflecting create, metadata-update, and delete mutations.
- Shared Chat module, identity prompt builder, and safe Process Monitor lifecycle through the separate Core Flow route.
- Live shared event delivery and final event-payload reconciliation for the GUI.
- Flow declares its route work plan, reports actual Flow-history loading and
  metadata-only registry loading, then records configured-LLM response composition
  and successful isolated exchange storage without exposing prompt or chat bodies.
