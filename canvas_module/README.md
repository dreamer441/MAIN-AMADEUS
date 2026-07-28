# AMADEUS Canvas

AMADEUS Canvas is the native spatial brainstorming and branching-conversation module.

The first implementation intentionally creates only the module boundary and visible infinite-style workspace. The Canvas is a structured scene, not a flattened screenshot. Future objects, connectors, context extraction, persistence, AMADEUS responses, handwriting, and Mind Map conversion will be added behind this module facade.

## Architecture

- `CanvasModule` is the Core-registered public facade.
- `CanvasWorkspaceDescriptor` exposes safe workspace metadata.
- `canvas_module.gui` owns PyQt rendering and is lazily imported.
- GUI code must call Core or the Canvas facade instead of owning future storage or LLM behavior.
- Runtime Canvas data will later live under `data/canvas/` and remain local.

## Current visible behavior

- Canvas appears as a persistent main navigation page.
- The workspace provides a large dark grid.
- Mouse dragging pans the view.
- The wheel zooms around the cursor.
- No structured objects or persistence are claimed yet.
