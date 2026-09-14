# Canvas Module Future Updates

## Next Implementation Phase

- Add richer title/comment styling, resizing, and optional comment shapes after the first attached-tab and draggable-oval implementation is validated.
- Add model availability checks and a friendly setup dialog when a selected Ollama profile is not installed.

- Preserve each workspace's viewport centre and zoom level across workspace switches and restarts.
- Add optional workspace restore UI for documents currently archived under `data/canvas/trash/`.
- Add per-branch or per-conversation send baselines instead of relying only on one workspace-wide semantic baseline.
- Add a visible send-history inspector showing instruction, model, exact target/support set, response object, and process run.
- Add follow-up controls for selecting which response target receives the automatic response arrow when several targets are sent together. The generated text already addresses all selected targets in one block.
- Add retry/regenerate operations without losing the failed or previous successful response history.
- Add explicit cancel support when the configured LLM/runtime supports interruption.

## Following Phases

- Named groups, collapse/expand, branch highlighting, and compressed group context.
- Duplicate, copy/paste, layering, and expanded locking controls.
- Add redo and optional persistent cross-session history; current Canvas undo is session-local.
- Add Canvas-to-Mind-Map projection controls, status, and filtering after the automatic source-backed block and connector projection is validated.
- Add read-only Mind Map projection status and filtering controls without allowing its managed Canvas records to edit or delete Mind Map source data.
- Stylus strokes, handwriting recognition, graph interpretation, and image injection.
- Visually distinct and fully undoable AMADEUS-created Canvas objects and diagrams.

## Core ownership cleanup — 2026-09-12

- Keep future GUI operations on the Core Canvas facade and projection validation in Canvas; preserve local Canvas document schemas.
## Code polish - 2026-09-14

- Keep future drawing behavior in Canvas graphics items, editing forms in Canvas dialogs, and workspace coordination in the view. Preserve explicit Core routes and avoid importing the workspace view from its helpers.
