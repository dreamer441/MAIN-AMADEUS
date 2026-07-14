# Shared Process Events Design

## Goal

Make the existing Process Monitor display genuine operational activity while an
active-chat request is running. This is an event-foundation task only: it does
not implement the Process Monitor V2 visual redesign, Inner Brain, persistent
jobs, Drift Mode, or Prompt Looping.

## Existing System Migration

`amadeus_trace` already owns a per-request `TraceSession`, `TraceEvent`, and
`TraceLogger`. It will be evolved in place rather than replaced by another
monitoring system. Existing module calls to `TraceLogger.add_event` remain
supported through a compatibility mapping to the new event fields.

The response payload will continue to include compact trace text, detailed
trace text, and structured trace events. This preserves existing consumers
while making the structured events the source of truth.

## Process Event Model

Replace the limited trace record with a validated `ProcessEvent` record. It
contains:

- `event_id`
- `run_id`
- optional `parent_event_id`
- `sequence`
- UTC `timestamp`
- `source_module`
- `brain_role`
- `event_type`
- `status`
- `title`
- `summary`
- optional `details`
- optional `progress`
- `metadata`

Validated enums define brain roles (`active`, `inner`, `system`), event types
(`run`, `objective`, `plan`, `step`, `decision`, `context`, `tool`,
`validation`, `warning`, `error`, `result`), and statuses (`pending`,
`running`, `completed`, `failed`, `paused`, `cancelled`). Unknown legacy trace
categories and levels map safely to system/step events and appropriate status.

Events describe observed operational activity and safe summaries only. Event
data must not include complete prompts, personal-memory values, source-file
contents, secrets, or raw hidden reasoning.

## Run And Live Delivery

`TraceLogger` remains the single small helper Core and modules use. Starting a
session assigns a unique `run_id` and initializes per-run event sequencing.
`add_event` records the structured event, then immediately invokes an optional
plain-Python event callback. The callback is optional and failure-isolated so
monitor delivery cannot prevent AMADEUS from returning a response.

There is intentionally no separate `ProcessEventEmitter` class or lifecycle
API in this phase. `TraceLogger` already owns the per-request event stream and
is the smallest compatible location for live callback delivery.

`ChatResponseWorker` creates the logger callback for active-chat requests. It
forwards each event through a PyQt signal. `AmadeusMainWindow` receives that
signal on the GUI thread and asks the existing right-panel monitor to append or
re-render the current structured event list. The backend neither imports nor
depends on PyQt.

At request start, MainWindow clears the current monitor and shows the first
real event as soon as it arrives. The final payload remains a reconciliation
snapshot for compatibility and worker-error fallback, not the normal source of
live updates.

## Initial Active-Chat Events

The normal non-annotation active-chat path emits genuine events in order:

1. Request received.
2. Request route selected.
3. Context building started.
4. Context building completed, listing only selected context types.
5. LLM request started.
6. LLM response received.
7. Final response returned.
8. Failure event when an exception occurs.

Core coordinates the route and passes the logger to feature modules. The
Context Builder and Chat/LLM integration report their own real context and LLM
activity through that logger; Core does not gain feature-specific monitoring
logic.

## Testing And Documentation

Tests cover enum validation, run IDs and event sequence, safe legacy mapping,
listener delivery, normal active-chat lifecycle, failure events, and PyQt
worker-to-window live-event forwarding. Existing trace payload compatibility is
also covered.

Update `amadeus_trace` documentation and feature/future documentation, plus
the global changelog. The changelog states that this task supplies only the
live shared-event foundation; Process Monitor V2, Inner Brain, and persistent
jobs remain future work.
