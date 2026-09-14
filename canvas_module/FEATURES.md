# Canvas Module Features

## Implemented

- First-class `CanvasModule` facade registered through AMADEUS Core.
- Stable workspace, document, typed-block, semantic-connector, root, sent-baseline, and send-operation domain models.
- Versioned per-workspace JSON persistence under `data/canvas/workspaces/` using Canvas document schema v6.
- Lightweight Canvas workspace registry at `data/canvas/registry.json` with last-active workspace restoration.
- Create, switch, rename, and archive/delete independent Canvas workspaces from the Canvas GUI.
- Each workspace owns separate blocks, connectors, root, semantic baseline, send history, and session-local undo stack.
- Legacy `data/canvas/<workspace>.json` files migrate safely into the workspace folder when the registry is initialized.
- Deleted workspace documents move to `data/canvas/trash/` for manual recovery instead of being permanently erased.
- Non-destructive loading of schema-v1, schema-v2, and schema-v3 workspaces, with migration on the next meaningful save.
- Atomic safe writes and explicit malformed-data failures.
- Persistent Canvas page in the main GUI navigation.
- Large infinite-style `QGraphicsScene` workspace with empty-space panning and cursor-centred bounded zoom.
- Typed text blocks with stable IDs, authorship, timestamps, dimensions, positions, and per-object revisions.
- Add, select, multi-select, drag, resize from a visible bottom-right handle, edit, and safely delete typed blocks.
- Optional block title tabs rendered as separate attached boxes above the main block.
- Optional oval block comments that remain attached and can be dragged around the block perimeter.
- Title and comment edits are semantic Canvas changes; moving the comment around the perimeter is layout-only.
- Fast text entry: Enter creates or saves a block, while Shift+Enter inserts a deliberate line break.
- Session-local Canvas undo through the toolbar or `Ctrl+Z`, restoring complete blocks, connectors, roots, baselines, and send records atomically.
- Two consecutive block right-clicks create a quick directional source-to-target arrow.
- Directional arrows and plain relationship lines with stable source/target IDs, labels, comments, relation types, and live attached geometry.
- Persistent manually selected Canvas root with a visible `ROOT` badge.
- Semantic fingerprint baseline that treats text/relationship edits as meaning changes while ignoring ordinary movement.
- Viewport, selection, and branch context modes.
- Arrow-aware ancestry/descendant traversal and plain-line peer traversal.
- Cycle-safe deterministic context ordering, token estimation, trimming, and explicit exclusions.
- Context preview separating response targets from directional history, descendants, peers, deletions, and warnings.
- Optional one-off instruction field beside `Send Changes to AMADEUS`; empty instructions are valid.
- Canvas model-weight selector with `Light` (`qwen3:4b`), `Normal` (`qwen3:14b`), and `Heavy` (`qwen3:32b`) routes each request without changing Flow Chat's model.
- The selected Canvas model weight is remembered through Qt settings.
- Background Canvas response worker using the existing Core route, configured LLM client, AMADEUS identity prompt, and shared Process Events.
- Target-focused Canvas prompt construction that answers changed/selected targets instead of every visible object.
- Multi-target prompts require one coherent response that handles every selected or changed block rather than choosing only one.
- Included graph connections are serialized explicitly, so several arrow-connected source blocks remain visible to the model as a combined reasoning path.
- Human-readable model prompts exclude Canvas object IDs and machine role labels, reducing metadata narration by local models.
- One automatic corrective retry rejects responses that still describe internal Canvas metadata instead of answering the target.
- AMADEUS responses are inserted as visually distinct, movable typed blocks.
- AMADEUS response blocks receive an initial height based on answer length and remain manually resizable.
- Successful responses receive a persisted directional `responds_to` connector from the primary target when available.
- Response placement searches predictable open space near the active targets and remains manually adjustable.
- Successful sends atomically persist the response block, response connector, exact context payload, optional instruction, rendered prompt, model name, process run ID, and new semantic baseline.
- Failed LLM requests do not mutate the Canvas or advance the baseline.
- Stale responses are rejected if the Canvas changes after context extraction and before commit.
- Optional instruction text clears only after success and remains available after failure.
- Lazy GUI imports so Canvas storage and domain tests do not require PyQt.

## Current Boundary

Canvas now supports multiple lightweight project workspaces and the first real spatial conversation loop with typed and resizable objects plus per-workspace session-local undo. Copy/paste, redo, persistent cross-session history, visual groups, per-branch baselines, handwriting, images, automatic Mind Map conversion, and AMADEUS-generated diagrams are not implemented yet.

- Resizable attached comment ovals with persisted dimensions.

- Canvas-specific Ollama requests disable reasoning-trace output so only the final answer is committed to the Canvas.
- Persisted Canvas blocks project to source-backed Mind Map `canvas` nodes using their stable `canvas_block` object IDs; Canvas-owned content, semantics, and layout remain authoritative.
- Persisted Canvas connectors project to source-backed Mind Map links using stable `canvas_connector` IDs, preserving connector relation type, label, and comment/evidence.
- Deleting a Canvas block or connector removes its projection. Deleting its projected Mind Map node or link deletes the Canvas source and synchronizes the resulting removal without recursive loops.
- Manual Mind Map node creation and Mind Map edits to Canvas-backed source content never create or edit Canvas blocks.
- The dedicated `mindmap_projection` Canvas workspace titled `Mind Map` is a read-only visualization of eligible Mind Map source nodes (`chat`, `sheet`, `memory`, `comment`, and `canvas_block`) and links whose endpoints are both eligible.
- Its managed blocks and connectors are locked, cannot be edited or deleted from Canvas, and carry projection metadata so they never re-enter the Canvas-to-Mind Map source bridge.

## Core ownership cleanup — 2026-09-12

- Canvas GUI operations use the explicit core.canvas facade. Workspace integration updates the managed Mind Map projection through the validated replace_mindmap_projection public API.
## Code polish - 2026-09-14

- Canvas presentation is organized into owner-local dialogs, graphics items and a surface, with the workspace view retaining coordination. Existing view imports remain available.
- Context role ordering uses one shared assignment loop while preserving selection, priority, distance tie-breakers and token budgets.
