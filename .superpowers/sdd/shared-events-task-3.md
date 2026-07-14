# Shared Process Events Task 3

Date: 2026-07-14

Implemented live normal-chat Process Monitor forwarding.

- `ChatResponseWorker` emits safe per-event rows through a PyQt signal before its final payload.
- Core accepts an optional framework-neutral event-row listener; it contains no PyQt imports.
- The Process Monitor incrementally renders structured rows and reconciles with the final payload.
- Material and annotation routes retain their existing final-payload behavior.

Validation:

- `py -3 -m unittest tests.test_annotation_gui tests.test_process_events -v` passed (25 tests).
- `py -3 -m compileall .` passed.
- `git diff --check` passed.

Known limitation: persistent process histories and Process Monitor V2 remain out of scope.
