# AMADEUS Canvas

AMADEUS Canvas is the native spatial brainstorming and branching-conversation module.

The Canvas is a structured scene, not a flattened screenshot. Typed ideas and their relationships are persistent domain objects with stable IDs and revisions; the PyQt scene only renders and manipulates those objects.

## Architecture

- `CanvasModule` is the Core-owned public facade for validated Canvas operations and atomic response commits.
- `CanvasConversationService` builds one target-focused prompt, calls the configured LLM boundary, and commits only successful, current responses.
- `CanvasTextBlock`, `CanvasConnector`, `CanvasSendOperation`, and `CanvasDocumentSnapshot` are framework-independent models.
- `CanvasContextBuilder` separates response targets from supporting context.
- Connectors reference source and target object IDs rather than fixed pixel endpoints.
- `CanvasWorkspaceRegistryStore` persists lightweight workspace titles and the last active workspace in `data/canvas/registry.json`.
- `CanvasDocumentStore` persists one versioned JSON document per workspace under `data/canvas/workspaces/`.
- Legacy root-level Canvas JSON files are migrated safely when the workspace registry is first created.
- Deleted workspaces are archived under `data/canvas/trash/` instead of being permanently erased.
- Schema v5 adds optional block titles, comments, and comment-perimeter positions while safely loading older Canvas schemas.
- Saves use atomic file replacement so interrupted writes do not partially overwrite the active workspace.
- `canvas_module.gui` owns rendering, worker-thread delivery, and explicit user interactions but does not write JSON directly.
- GUI presentation helpers live in `gui/dialogs.py`, `gui/items.py`, and `gui/surface.py`, with shared defaults in `gui/constants.py`. `gui/view.py` coordinates the workspace and worker and preserves the existing helper imports.
- GUI imports remain lazy so non-GUI Canvas code can be tested without PyQt.

## Workspace workflow

The Canvas window now supports several lightweight project workspaces. Use the workspace selector and `New`, `Rename`, and `Delete` controls above the Canvas toolbar.

- Creating a workspace activates a new empty Canvas with a stable generated ID.
- Switching workspaces restores that workspace's own blocks, connectors, root, sent baseline, and AMADEUS send history.
- The last active workspace is restored when AMADEUS starts again.
- Undo history is session-local but isolated per workspace, so `Ctrl+Z` never restores objects from another project.
- Deleting a workspace removes it from the selector but archives its JSON document for manual recovery.
- If the final workspace is deleted, AMADEUS creates a new blank `Main Canvas` automatically.

This first version intentionally avoids folders, nested workspace hierarchies, tags, and multiple simultaneously open Canvas instances.

## Context semantics

The viewport does **not** mean AMADEUS should answer every visible block.

- New or meaningfully edited blocks/connectors are response targets.
- Explicit selection can define a target, especially before the first send.
- The visible viewport limits which supporting objects are eligible.
- Incoming arrows reconstruct the directional history toward a target.
- Outgoing arrows provide existing follow-up/descendant context.
- Plain lines add related peer concepts of similar semantic weight.
- Moving a block is a layout change and does not make it a semantic response target.
- The optional instruction is one-off request metadata. It may be empty and does not become a Canvas object automatically.
- Optional title tabs and oval comments are part of the block's semantic content and are included in context; moving only the comment oval is treated as layout.
- Click an oval comment once to reveal its resize handle; moving or resizing the oval remains layout-only and persists per workspace.

## Canvas conversation workflow

1. Arrange the viewport and choose Viewport, Selection, or Branch context.
2. Choose Light (`qwen3:4b`), Normal (`qwen3:14b`), or Heavy (`qwen3:32b`) for this Canvas request.
3. Optionally type a short instruction such as `critique this` or `turn this into tasks`.
4. Press `Send Changes to AMADEUS`.
5. Core routes the request to `CanvasConversationService` on a background worker.
6. AMADEUS answers the changed or selected targets using arrow history and line peers as support.
7. The response appears as a movable AMADEUS block near the source.
8. A `responds_to` arrow is created from the primary target when possible.
9. The response, link, exact context package, prompt, instruction, model, process run, and new baseline are saved together.

If the LLM fails, nothing is added and the optional instruction remains. If the Canvas changes while the LLM is working, the stale answer is rejected instead of being attached to the wrong state.

The model-facing prompt is deliberately human-readable and excludes internal object IDs and role labels. If a local model still returns Canvas metadata instead of a real answer, the service requests one direct correction. A second metadata-only response is rejected and no useless block is committed.

## Current visible behavior

- Create, move, resize, edit, select, multi-select, and delete typed blocks.
- Press Enter in the block editor to create/save immediately; use Shift+Enter for a new line.
- Undo the latest Canvas mutation with the toolbar button or `Ctrl+Z`. Undo is session-local and restores the complete structured scene state.
- Select a block and drag its bottom-right handle to resize it; resize is layout-only and does not create a new semantic target.
- Select exactly one block to unlock `Title` and `Comment`; titles appear as attached tabs above the block and comments as draggable oval notes around its perimeter.
- Right-click a source block and then right-click a target block to create a quick directional arrow.
- Create and edit semantic lines/arrows that remain attached while blocks move.
- Mark one persistent root block.
- Preview target/support context before sending.
- Choose Light, Normal, or Heavy model weight for each send; Heavy uses the installed `qwen3:32b` Ollama model.
- Add an optional instruction or leave it blank.
- Send through AMADEUS’s existing local model infrastructure without freezing the GUI.
- Select or change several prompt blocks and receive one response that addresses all of them; explicit arrow/line flow is included in the model-facing context.
- Receive a movable, resizable, visually distinct AMADEUS response directly inside the Canvas; long answers start with a taller block.
- Create, switch, rename, and archive multiple independent Canvas workspaces.
- Reopen the last active workspace with its complete scene and send history after restarting AMADEUS.

## Current boundary

Each Canvas workspace currently uses one workspace-level sent baseline. Undo history lasts for the current AMADEUS session; redo and persistent cross-session history are not implemented. Per-branch conversation histories, groups, copy/paste, handwriting, images, and Mind Map conversion remain future work.

## Model request diagnostics

Canvas checks that the selected Ollama model is installed before generation, disables thinking-trace output for the Canvas call, shows the active model while waiting, and displays a visible warning dialog instead of failing silently.
