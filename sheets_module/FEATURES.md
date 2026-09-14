# Sheets Module - Current Features

- Stores sheets locally in `data/sheets/sheets.json`.
- Supports global sheets and current-chat sheets.
- Each sheet has:
  - `sheet_id`
  - title
  - description
  - scope
  - chat id when chat-scoped
  - editable content
  - created/updated timestamps
- Provides a service layer so Core/GUI do not directly edit JSON storage.
- Provides right-panel payloads for the Sheets tab.
- Supports `[sheet]` annotation behavior:
  - `[sheet]` opens all visible sheets in the right panel.
  - `[sheet][list]` opens all visible sheets.
  - `[sheet][chat]` opens current-chat sheets.
  - `[sheet][global]` opens global sheets.
  - `[sheet][chat][Sheet Title]` opens one chat sheet.
  - `[sheet][global][Sheet Title]` opens one global sheet.
  - `[sheet][scope][Sheet Title] prompt` injects that sheet as callable context for the prompt.
- Explicitly separates sheet context from always-active memory.

## Mind Map projection

- Sheets created or edited through Core are projected into stable source-backed Mind Map nodes.
- Chat-scoped sheets receive a relationship to their owning chat and are available as default linked context.

## Core ownership cleanup — 2026-09-12

- resolve_target accepts plain scope and locator values; Sheets no longer imports Annotation parser types. A structural resolve_annotation_target compatibility method preserves existing callers.
