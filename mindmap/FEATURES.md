# Mind Map Features

## Implemented foundation

- Real Mind Map page replaces the former GUI placeholder.
- Zoomable, selectable `QGraphicsView` graph canvas.
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
- Framework-independent graph-change subscriptions so external creation can appear live in the GUI. Public Core notifications contain only operation/entity identifiers, graph ID, and timestamp; views refresh their snapshot through Core.
- Real ordered `ProcessEventEmitter` operation events for node and link mutations, with generic summaries that exclude private graph data and raw errors.
- Core registration under the stable name `mind_map`.
- Core wrappers keep GUI and future callers out of SQLite internals.
- SQLite database paths must be relative to and contained by the configured project root.
- Mind Map snapshot, search, mutation, import, export, and layout persistence run in Qt workers, with controls disabled until each operation completes or fails.
- Automated tests for persistence, links, cascade deletion, source upsert, retrieval, events, validation, and JSON round trips.
