# AMADEUS Mind Map / Relevance Graph

The Mind Map is AMADEUS's local structured relationship system. It stores meaningful objects as nodes, stores relationships as first-class links, and presents them as a living relevance space rather than a generic database editor.

## Architecture

The current module deliberately combines two strengths:

- **Current AMADEUS foundation:** immutable graph models, Core-mediated operations, SQLite persistence, safe process events, source identity, JSON backup, and tests.
- **Earlier AMADEUS Mind Map behaviour:** force-directed organization, importance/relevance prominence, central and pinned nodes, local-neighborhood focus, source previews, and direct navigation back to AMADEUS objects.

The GUI never writes SQLite directly. User actions, Chat Registry imports, future Creation Module proposals, and future Graph Curator operations all pass through `MindMapModule` and `MindMapService`.

## Current workspace behaviour

- Resizable Explore / Graph / Context panels.
- Type-coloured graph nodes with relevance-based size, opacity, and depth.
- Typed link physics, directed arrows, temporary-link styling, and visible relationship evidence.
- Central-node gravity and pinned/locked layout behaviour.
- Selecting one node keeps its direct neighborhood bright and fades unrelated graph objects.
- Context, persisted details, and direct relationships are inspectable in separate tabs.
- Double-clicking a source-backed node asks `MainWindow` to open its owning chat, sheet, material, or message location.
- Dedicated chats can be manually imported through **Import Chats**. Import uses source upsert identity, so repeating the operation updates the same graph nodes rather than creating duplicates.
- Manual nodes remain editable graph objects; double-clicking one opens its editor.

## Chat and reasoning retrieval

`[mindmap]` retrieval now asks the public Mind Map API for a bounded context package. Search results are expanded through explicit graph links, so the LLM receives:

- seed nodes that matched the request;
- connected context nodes;
- relationship direction and type;
- link strength, confidence, permanence, and evidence;
- source references when present.

The retrieval layer does not infer missing links and does not access SQLite directly.

## Persistence and safety

The active graph is stored under:

```text
data/mindmap/mind_map.sqlite3
```

SQLite remains the source of truth. Visual physics never persists automatically. Coordinates are written only after explicit drag or layout actions through Core. Replacement JSON imports validate the complete graph before a single transaction changes storage.

Graph-change subscriptions remain invalidation notices containing identifiers only. Private node content, descriptions, evidence, and metadata are loaded through the normal snapshot API and are never published in graph-change events.

## Main files

- `models.py` — graph nodes, links, snapshots, neighborhoods, source references, and LLM context packages.
- `repository.py` — SQLite schema and persistence.
- `service.py` — graph authority, validation, retrieval, context building, events, and import/export.
- `mind_map_module.py` — stable public facade.
- `gui/physics.py` — transient living graph projection.
- `gui/items.py` — node/link presentation and interaction.
- `gui/dialogs.py` — node/link editors and chat-import selection, including shared unit-interval controls.
- `gui/surface.py` — canvas zoom, background grid, and pointer navigation.
- `gui/view.py` — Mind Map workspace orchestration using Core only; preserves existing dialog, surface, and type-constant imports.

## Boundaries for future intelligence

The Mind Map service validates and stores. A future Graph Curator LLM may analyze chats and propose nodes, links, metadata, and summaries, but it must not write SQLite directly. Proposed operations should pass through validation and review before the service applies them.

## Workspace-backed node types

`chat`, `sheet`, `comment`, and `memory` can create real AMADEUS objects when the Create Node dialog keeps **Create the matching real AMADEUS object** enabled. Other types are graph-only. Direct relationships to a chat are injected into that chat by default; edit the link and disable **Automatically include this linked node in chat context** to keep the relationship visual-only.
