# Side Panel Features

## Implemented Now

- Added a dedicated `side_panel` module.
- Added `SidePanelPayload` as the stable structure for GUI panel updates.
- Added `SidePanelState` as runtime state for the right-side workspace.
- Supports current panel types:
  - `process`
  - `code`
  - `memory`
- Keeps unknown future panel payloads in a safe `extra_payloads` dictionary.
- Provides a future-ready `current_context_text()` method for planned `[panel]` annotation support.

## Responsibility Boundary

The Side Panel module only owns panel payload/state logic.

Content remains owned by the correct module:

- `amadeus_trace` creates trace data.
- `project_file_reader` reads files.
- `memory_module` stores and lists memory.
- Future sheets/materials modules will own their own content.

The side panel displays and tracks visible workspace state; it does not create the underlying knowledge.

## Sheets and Materials Tabs

- Added editable `Sheets` tab.
- Added read-only `Materials` tab foundation.
- Side panel now supports payload types: `code`, `memory`, `sheets`, and `materials`.
- Sheets tab emits save/delete requests to MainWindow/Core instead of writing storage directly.

## Materials Payloads

- Materials tab now displays exported chat lists and selected message ranges.
- Materials payload metadata includes export ids, selected message numbers, and file paths.

## Export Segment Display Accuracy

- Materials payloads for export ranges now label selected ranges as verified exported chat text, not metadata.
- Selected message numbers remain visible in payload metadata for future clickable range tools and Mind Map source links.

## Side Ask and Comments Panels

- Added Side Ask tab for secondary Q&A.
- Added Comments tab for current-chat comments.
- Right panel can now host interactive tools, not only read-only payloads.

## Side Ask and Comments Panel Polish V1.1

- Side Ask panel includes a manual context box separate from the question/answer flow.
- Comments panel headings expose target message numbers in a readable `comment(number)` format.
- Right-panel comment display is prepared for future message metadata and visual message-number badges.
