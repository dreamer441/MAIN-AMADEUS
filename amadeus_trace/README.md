# AMADEUS Trace Module

`amadeus_trace` provides the shared AMADEUS Process Monitor foundation.

It records structured execution events that actually happen while AMADEUS handles one user message. It is not a hidden-thinking viewer and must never invent private reasoning or fake chain-of-thought.

The trace flow is simple:

1. Core creates a new trace session for the user message.
2. Core and modules add real events such as input received, annotation check, routing decision, LLM call, errors, and output ready.
3. The GUI receives safe event rows while a normal chat is running, then reconciles
   the monitor with Core's completed response payload.

Trace sessions are per-message so the latest monitor view stays focused and does not mix old routing events with the current request.

## Event Model And Lifecycle

`ProcessEvent` is an immutable, validated record for a real operational event. It
contains an ordered sequence within one run, a UTC timestamp, source module,
brain role, type, status, safe title and summary, plus optional details,
progress, metadata, and parent event ID. Event metadata is copied so later caller
changes cannot alter a recorded event.

`ProcessEventEmitter` owns one run at a time. Call `start_run()` before `emit()`,
then close it with exactly one `complete_run()` or `fail_run()`. Events cannot be
recorded before a run starts or after it reaches a terminal state. `events`
returns an immutable snapshot of the recorded event list.

`subscribe(listener)` registers a framework-independent callback for future
events. Delivery is immediate and listener failures are isolated: monitoring
listeners cannot interrupt event recording or the user request. The emitter has
no PyQt dependency.

## GUI Bridge And Safety Boundary

For normal chat requests, Core accepts an optional framework-neutral event-row
listener. The GUI worker adapts that listener to a PyQt signal and incrementally
renders the rows in Process Monitor before the final response arrives. The final
payload remains authoritative and replaces the incremental state. Annotation,
material, and other non-normal-chat routes retain final-payload rendering.

The monitor is diagnostic only. Events must describe real code execution and use
safe operational summaries. It must never expose private reasoning, invent
chain-of-thought, or let monitoring failures affect chat execution.

## Compatibility

`TraceLogger` remains the module-facing compatibility facade. It maps legacy
category and level calls onto validated process events while preserving historic
compact/detailed text and legacy payload category fields. Its silent legacy
session start preserves the established empty monitor until the first explicit
trace event.
