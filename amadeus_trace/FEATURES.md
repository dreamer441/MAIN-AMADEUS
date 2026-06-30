# Features

- Per-message trace sessions.
- Structured `TraceEvent` records with category, title, message, timestamp, and level.
- Compact and detailed text rendering.
- Safe `TraceLogger` wrapper so monitoring failures do not break chat.
- GUI-ready structured event list for future filters and exports.
- Designed to show real execution events only, not hidden internal thoughts.

Current event categories include:

- system
- input
- annotation
- routing
- file
- llm
- module
- output
- error
