# Phase 6 Final Fix Report

## Scope

Implemented only the two accepted final-review fixes. The requested export-count finding was not implemented because the existing export range display satisfies the required message range OR message count behavior.

## Fixes

- Unknown selection comments now use `Comment(?)`; `Comment(A)` remains reserved for general comments.
- The Comments panel describes unknown selections as `Selected text (message unknown)`, retains `Selection` type, and disables Jump.
- MainWindow finds a jump target only when a QTextDocument block begins with the rendered `[number] ` header. A bracketed number inside earlier message content cannot be selected as a target.

## Test Coverage

- Added storage/payload coverage for a selection without a detected message number.
- Added Comments-panel coverage for selector label, selection details, and disabled Jump.
- Added a MainWindow regression for misleading `[12] ` content before the actual `[12]` message header.

## Validation

- `py -3 -m unittest tests.test_comments_module -v`: passed 5 tests.
- `py -3 -m unittest tests.test_annotation_gui -v`: passed 12 tests.
- `py -3 -m unittest discover -s tests -v`: passed 44 tests.
- `py -3 -m compileall .`: completed successfully.
