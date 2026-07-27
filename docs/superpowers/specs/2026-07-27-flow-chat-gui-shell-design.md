# Flow Chat GUI Shell Design

## Goal

Make Flow Chat the permanent AMADEUS home conversation while preserving the existing dedicated-chat workspace and its side-panel features.

## Architecture

`AmadeusMainWindow` becomes a navigation shell with a persistent sidebar and stacked module views. The existing dedicated-chat interface is moved behind a reusable Chats view without changing its Core-only service boundary. Flow Chat is a separate view and Core route.

Core composes a `FlowChatStore`, `ChatRegistry`, and `FlowContextBuilder`. The Flow route uses the existing `AmadeusChatModule`, injected LLM client, identity prompt builder, and shared `TraceLogger`/`ProcessEventEmitter` system. GUI workers remain Qt adapters: background work emits events and final payloads through signals, while widgets update only on the GUI thread.

## Persistence

Flow Chat uses a dedicated JSONL store under `data/flow_chat/`. It is deliberately not a protected ordinary chat because ordinary-chat selectors, deletion controls, exports, active-chat context, and per-chat side panels must not accidentally operate on Flow history. The store has safe index/message parsing and atomic metadata writes where it writes an index.

## Context

Flow context implements only the first two memory layers:

1. Recent Flow messages from the Flow store.
2. Dedicated-chat `chat_id`, title, and description from `ChatRegistry`.

`ChatRegistry` wraps `ChatHistoryStore` and never loads dedicated-chat messages. It reads current metadata for every Flow request, so creation, rename, description changes, and deletion are visible without restarting AMADEUS. The context builder formats this metadata in a dedicated section and tells the model it is not chat history.

## GUI

The shell exposes Flow Chat, Chats, Code, Mind Map, and Habit Tracker. Flow Chat is selected at startup. Chats retains the current conversation workspace and right-side Process Monitor. Code, Mind Map, and Habit Tracker are explicit named placeholder views so navigation and future view ownership are visible today. Views are created once and retained by the stack, preserving their state across navigation.

## Events and Errors

Flow requests emit genuine lifecycle events for request receipt, context construction, registry loading, LLM boundaries, persistence, output delivery, and failure. Events carry the existing run ID and omit prompts, message bodies, and secrets. Core closes each run successfully or as failed. Worker errors produce safe error payloads and restore input controls.

## Testing

Focused tests cover Flow persistence, registry metadata isolation and live updates, Flow context formatting, lifecycle event order and failed runs, and shell navigation/default-state preservation. Existing tests remain the regression suite.

## Scope Limits

This design does not add summaries, deep chat retrieval, semantic search, voice, proactive behavior, full Code/Mind Map/Habit modules, automatic routing, or a second event system.
