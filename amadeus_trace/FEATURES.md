# AMADEUS Trace / Process Monitor Features

## Implemented Now

- Validated immutable `ProcessEvent` records with safe summaries, UTC timestamps,
  ordered sequences, optional parent IDs/progress/details, and copied metadata.
- Framework-independent `ProcessEventEmitter` lifecycle API with immediate,
  fault-isolated listener delivery.
- `ProcessEventEmitter.start_run()`, `emit()`, `complete_run()`, and `fail_run()`
  enforce one ordered run with no events before start or after terminal state;
  `events` exposes an immutable recorded-event snapshot.
- `subscribe(listener)` delivers future events immediately and isolates listener
  failures so observability cannot interrupt request execution.
- `TraceLogger` compatibility facade that maps legacy trace categories and levels
  to validated events while preserving compact/detailed text and legacy payload keys.
- Legacy `file`, `llm`, `annotation`, `module`, and `routing` categories remain
  visible in compatibility payloads and detailed text even where they share a
  validated event type.
- Completed or failed emitter runs reject subsequent events and duplicate terminal actions.
- Legacy `TraceLogger.start_session()` creates its emitter run silently so empty
  sessions retain their historic empty Process Monitor output.
- Per-message trace sessions.
- Structured `TraceEvent` records with category, title, message, timestamp, and level.
- Compact and detailed text rendering.
- Safe `TraceLogger` wrapper so monitoring failures do not break chat.
- `TraceLogger` exposes safe `complete_run()` and `fail_run()` lifecycle terminals to its module callers.
- `TraceLogger.has_failed_event()` lets Core finalize a run after a module records an operational failure.
- GUI-ready structured event list for future filters and exports.
- Designed to show real execution events only, not hidden internal thoughts.
- Shows deterministic project file inspection route events when Core bypasses the LLM for exact file/folder questions.
- Comments now explicitly mark the safety boundary between real execution trace and fake/hidden reasoning.

Normal active-chat lifecycle emission is integrated at Core, Context Builder, and
Chat boundaries. Normal chat now forwards safe structured event rows live through
a framework-neutral Core listener and GUI PyQt signal; the final Core payload
reconciles the Process Monitor after the response completes.

The Process Monitor is limited to real, safe operational events. It does not
expose hidden reasoning or chain-of-thought, and listener failures cannot affect
the underlying chat request.

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
