# Mind Map Features

## Implemented foundation

- Real Mind Map page replaces the former GUI placeholder.
- Zoomable, selectable `QGraphicsView` graph canvas.
- Three-panel PyQt6 workspace: grouped Nodes/Actions tabs, force-directed graph space, and Context/Node Details tabs.
- Type-coloured, importance/relevance-sized node circles with selected, hover, pinned, and central visual states.
- Canvas pan/zoom, direct node drag, focus, fit, deterministic force layout, linked-node recentering, pin, and central controls.
- A node is immovable when either its persistent position lock or `mindmap_pinned` metadata is true; metadata cannot override a persistent lock. Pin and central state persist through Core node metadata updates and remain preserved when source adapters refresh their metadata; force simulation itself is in-memory and never writes storage.
- Create, edit, move, lock, search, and delete nodes.
- Create, edit, inspect, and delete directed first-class links.
- Explicit source-node selection when creating a directed relationship.
- Node properties: type, title, description, content, importance, confidence, status, position, lock state, source reference, metadata, timestamps.
- Link properties: type, label, strength, confidence, permanence, evidence, temporary state, expiry/decay fields, usage and reward/punishment placeholders, source reference, metadata, timestamps.
- SQLite persistence with foreign keys, cascade deletion, indexes, WAL mode, and source identity uniqueness.
- Portable JSON graph export and fully validated JSON import; replacement imports are one SQLite transaction, so invalid records or write failures preserve the prior graph.
- Search across title, type, description, and content.
- Bounded local-neighborhood retrieval up to five graph steps.
- Generic `upsert_source_node` integration seam for Chat Registry, Sheets, Materials, Memory, and the future Creation Module.
- Framework-independent graph-change subscriptions so external creation can appear live in the GUI. Public Core notifications contain only operation/entity identifiers, graph ID, and timestamp; subscriptions can be removed when a view closes or is destroyed.
- Real ordered `ProcessEventEmitter` operation events for node and link mutations, with generic summaries that exclude private graph data and raw errors.
- Core registration under the stable name `mind_map`.
- Core wrappers keep GUI and future callers out of SQLite internals.
- SQLite database paths must be relative to and contained by the configured project root.
- Mind Map snapshot, search, mutation, import, export, and layout persistence run in Qt workers, with controls and canvas input disabled until each operation completes or fails. Layout coordinates persist through one atomic batch transaction.
- Automated tests for persistence, links, cascade deletion, source upsert, retrieval, events, validation, and JSON round trips.
- Focused deterministic physics, scene-reconciliation, bounded-timer, and GUI state tests.
- Legacy-compatible dark title/subtitle/status typography, framed three-panel layout, tabs, controls, borders, and spacing for the Mind Map page.
- Incremental scene reconciliation preserves unchanged node and link item identities across graph snapshots; normal refreshes do not clear and recreate the scene.
- Bounded 33 ms visual-only physics timer stops after stable motion or a fixed tick cap. Live motion is capped at 120 nodes and synchronous force layout at 80 nodes to avoid quadratic GUI-thread work on large graphs.
