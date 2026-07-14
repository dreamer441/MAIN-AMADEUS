# AMADEUS Trace / Process Monitor Features

## Implemented Now

- Validated immutable `ProcessEvent` records with safe summaries, UTC timestamps,
  ordered sequences, optional parent IDs/progress/details, and copied metadata.
- Framework-independent `ProcessEventEmitter` lifecycle API with immediate,
  fault-isolated listener delivery.
- `TraceLogger` compatibility facade that maps legacy trace categories and levels
  to validated events while preserving compact/detailed text and legacy payload keys.
- Legacy `file`, `llm`, `annotation`, `module`, and `routing` categories remain
  visible in compatibility payloads and detailed text even where they share a
  validated event type.
- Completed or failed emitter runs reject subsequent events and duplicate terminal actions.
- Per-message trace sessions.
- Structured `TraceEvent` records with category, title, message, timestamp, and level.
- Compact and detailed text rendering.
- Safe `TraceLogger` wrapper so monitoring failures do not break chat.
- GUI-ready structured event list for future filters and exports.
- Designed to show real execution events only, not hidden internal thoughts.
- Shows deterministic project file inspection route events when Core bypasses the LLM for exact file/folder questions.
- Comments now explicitly mark the safety boundary between real execution trace and fake/hidden reasoning.

The shared-event backend is a foundation only. Core and feature-module lifecycle
emission plus the live GUI bridge are intentionally separate follow-up tasks.

## Current Event Categories

- system
- input
- annotation
- routing
- file
- llm
- module
- output
- error
