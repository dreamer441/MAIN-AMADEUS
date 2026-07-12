# AMADEUS Trace / Process Monitor Features

## Implemented Now

- Per-message trace sessions.
- Structured `TraceEvent` records with category, title, message, timestamp, and level.
- Compact and detailed text rendering.
- Safe `TraceLogger` wrapper so monitoring failures do not break chat.
- GUI-ready structured event list for future filters and exports.
- Designed to show real execution events only, not hidden internal thoughts.
- Shows deterministic project file inspection route events when Core bypasses the LLM for exact file/folder questions.
- Comments now explicitly mark the safety boundary between real execution trace and fake/hidden reasoning.

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
