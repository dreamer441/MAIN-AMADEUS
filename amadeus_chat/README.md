# AMADEUS Chat Module

The Chat module owns normal conversation behavior.

Chat does not read files, control the GUI, or decide global identity. Core provides any relevant context, and Chat sends that context to the LLM client through one stable prompt shape.

The Identity Module is injected through Core so AMADEUS responds from her global identity without hardcoding the full charter inside Chat.

## Memory-Aware Chat

Chat accepts memory context from Context Builder and keeps it in a separate prompt section so AMADEUS can use durable memory without mixing it with the latest user instruction.

## Flow Reuse Boundary

Flow reuses this module's LLM prompt and response path through Core, but Flow context is built by `flow_chat`, not by the dedicated-chat Context Builder path. Its prompt context keeps Layer 0 recent Flow history separate from Layer 1 dedicated-chat metadata. Dedicated-chat message bodies are not supplied to Chat for Flow requests.
