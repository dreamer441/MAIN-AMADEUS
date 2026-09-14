# Mind Map Features

## Graph foundation

- Immutable framework-independent node, link, snapshot, neighborhood, source-reference, and context-package models.
- SQLite graph persistence with source identity uniqueness, foreign keys, cascading link deletion, indexes, WAL mode, atomic position updates, and validated replacement imports.
- Stable `MindMapModule` facade registered as `mind_map` in Core.
- Core-mediated create, edit, move, delete, search, neighborhood, source upsert, import, and export operations.
- Safe ordered ProcessEvent operation traces and identifier-only graph-change notifications.

## Living graph workspace

- Resizable Explore / Graph / Context panels inside the AMADEUS shell.
- Quiet infinite graph canvas with pan, bounded zoom, grid, fit, and keyboard shortcuts.
- Type-coloured nodes with relevance/importance-based radius, opacity, and depth.
- Pinned and central visual states, central-node gravity, deterministic overlap separation, and typed-link spring strengths.
- Clean straight relationship lines with type-specific colours, temporary-link dashes, evidence tooltips, and a selectable midpoint detail control.
- Selecting a node highlights its direct neighborhood and fades unrelated nodes and links.
- Separate Context, Details, and Connections panels.
- Grouped node browser, search, direct focus, force layout, linked-node recentering, and JSON controls.
- Incremental scene reconciliation preserves existing graphics items across snapshots.
- Bounded visual physics timer stops after stability, wakes during node drag, lets neighbors react, and resumes after explicit position persistence.
- Cached batched background-grid drawing reduces repaint cost while panning and dragging.
- Ordinary node clicks remain selection-only; graph physics starts only after a real drag threshold is crossed.
- Active node dragging uses a temporary low-cost repaint mode and restores full antialiasing on release.
- A visible header-level **Edit Node** button opens the same complete node editor used by the Actions panel.

## AMADEUS integrations

- Manual **Import Chats** workflow projects selected Chat Registry entries into stable source-backed graph nodes.
- Reimporting a chat updates its existing graph node through `(graph_id, source_type, source_id)` identity.
- Double-click source navigation is coordinated by `MainWindow`; the Mind Map never manipulates chat/sheet/material widgets directly.
- Source-backed chat, message, sheet, and material nodes can return to their owning AMADEUS workspace.
- Generic source upsert remains available for Memory, Sheets, Materials, Creation Module, and future adapters.

## Retrieval

- `[mindmap][query] question` and `[mindmap] question` remain available.
- Retrieval uses a bounded public context package rather than direct repository access.
- Search seeds expand through explicit graph neighborhoods and include relationship direction, strength, confidence, permanence, evidence, and source references.
- Compatibility fallback remains for older injected Mind Map facades used by tests.

## Validation

- Core and physics tests pass in a headless environment.
- Existing annotation retrieval lifecycle tests remain compatible.
- PyQt GUI source compiles successfully; final interactive validation must run on the Windows AMADEUS environment where PyQt6 is installed.

## Chat workspace synchronization

- `chat`, `sheet`, `comment`, and `memory` nodes can represent real source-backed AMADEUS objects; other types remain graph-only.
- New chats, chat-scoped sheets, comments, and explicit memory entries synchronize into stable graph nodes.
- Direct links to a chat are default-active prompt context unless the link sets `inject_into_chat` to false.
- A right-panel Linked tab exposes active and disabled graph context for the current chat.
- Source-backed Sheet and Comment nodes carry their owning chat locator for two-way navigation.
- Existing legacy chats are synchronized on demand rather than bulk-imported automatically.
- Deleting a source-backed Chat, Sheet, Comment, or Memory node through Mind Map deletes the corresponding real workspace object by default.
- The delete confirmation distinguishes graph-only deletion from deletion that also removes real AMADEUS workspace data.
- Source-backed node types cannot be converted in-place because type identifies the owning AMADEUS module; graph-only node types remain editable.

## Grounded Chat context

- Direct linked context is formatted as literal records with separate Title, Node Type, Source ID, Description, Content, and Relationship fields.
- Exact content is placed between visible delimiters so local models can distinguish stored text from prompt instructions.
- Chat rules explicitly forbid invented labels, categories, IDs, relationships, sheet contents, and reinterpretation of non-memory nodes as memory.
- Exact linked/retrieved records override older assistant guesses about the same graph objects.

## Inner Brain Chat Metadata

- Existing source-backed chat nodes retain their `chat` type while exposing stored Inner Brain short summaries, detailed summary, and export reference in node metadata.
- Refreshing Chat Data resynchronizes the existing chat source node; it creates no additional graph nodes or exports.

## Canvas source projection

- Persisted Canvas blocks project as source-backed `canvas` nodes identified by `canvas_block` source references and render as rounded rectangles; existing chat-backed nodes remain elliptical.
- Persisted Canvas connectors project as source-backed links identified by `canvas_connector` source references, mapping Canvas relation type, label, and comment to link type, label, and evidence.
- Canvas deletion removes projected nodes and links. Deleting a Canvas-backed Mind Map node or link deletes the owning Canvas block or connector and lets the Canvas event reconcile the graph.
- Manual Mind Map node creation and source-content editing do not create or edit Canvas blocks. Only Canvas-created objects participate in this projection.

## Read-only Canvas projection

- Mind Map reconciles eligible source-backed `chat`, `sheet`, `memory`, `comment`, and `canvas_block` nodes into the dedicated `mindmap_projection` Canvas workspace titled `Mind Map`.
- Graph links mirror as Canvas connectors only when both endpoint nodes are eligible. Reconciliation removes stale managed records but preserves ordinary Canvas records in that workspace.
- Managed projection blocks and connectors are locked visual records: Canvas cannot edit or delete them, and their metadata prevents Canvas events from being projected back into Mind Map.
- Canvas-backed Mind Map nodes retain their rounded-rectangle rendering with compact fixed `84 x 40` geometry; non-Canvas nodes retain the circular treatment.

## Core ownership cleanup — 2026-09-12

- Cross-module source synchronization is owned by workspace_integration; mindmap.integrations remains a compatibility import. Graph operations and persistence stay in Mind Map.
