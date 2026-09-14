# Core ownership cleanup

Date: 2026-09-12

## Approved outcome

Core registers modules and routes requests through explicit public interfaces.
Existing features, local data formats, approval semantics, and visible request
results remain available. Application setup constructs dependencies. Feature
workflows belong to the module that executes them, not to a renamed Core class.

## Ownership

- `amadeus_app`: application composition; constructs services and supplies named
  routes to Core. No domain decisions or GUI construction.
- `amadeus_core`: stable public facade, registry, and explicit forwarding methods.
  No feature-specific prompts, persistence decisions, annotation interpretation,
  metadata workflows, or imports of feature internals.
- `chat_workspace`: dedicated-chat execution, lifecycle, metadata, selected
  context requests, and workspace-facing operations. Chat generation stays in
  `amadeus_chat`; selection stays in `context_builder`; storage stays in stores.
- `flow_chat`: complete Flow request handling, including its command routes and
  isolated history. Habit command execution belongs to `habit_tracker`.
- `canvas_module`: existing Canvas execution, persistence and context generation;
  a request adapter returns the existing response contract.
- `permissions`: existing pending action validation and single-use approvals;
  dispatch through registered owner callbacks. No invented filesystem or shell
  permission capabilities.
- `workspace_integration`: source synchronization between graph, Canvas, chats,
  sheets, comments and memory; dependencies supplied explicitly at startup.
- `annotation_module`: parse syntax and resolve context/results. It does not
  execute a full conversation or persist conversation history.

## Boundaries and compatibility

GUI operations route through Core. Canvas uses explicit Core-facing methods;
Habit Tracker uses the application's shared service through a Core facade.
Existing module entry imports remain supported where inexpensive compatibility
exports avoid breaking callers. Compatibility files contain no feature logic.
Cross-module calls use public APIs; Sheets receives plain scope/locator values
rather than depending on Annotation parser types. Module-specific helpers remain
within their owner folders. Global identity remains separate from response modes.

## Validation

Capture baseline source and run existing tests against it. Add focused tests for
Core delegation, dependency direction, approval lifecycle, shared Habit service,
and GUI routing. Run regression tests with temporary data and an offscreen Qt
platform. Run `python -m compileall .` before committing; any failure blocks commit
and push. Document runtime/environment limitations honestly.

## Delivery

Update affected module docs and the architecture map. Deliver a complete cleanup
change inventory plus manual checks for conversations, annotations, approval,
Canvas, Mind Map synchronization, Habit Tracker and restart persistence. Stage
only reviewed source/configuration/documentation; exclude all runtime data.

## Scope limits

This is a behavior-preserving ownership refactor. It does not reset local data,
remove existing features, add a plugin framework, implement a reasoning engine,
or introduce new model/network dependencies.
