# AMADEUS Mind Map / Relevance Graph

The Mind Map is AMADEUS's local structured relationship system. It stores meaningful objects as nodes, stores relationships as first-class links, and exposes the same validated graph API to Dato's GUI and future AMADEUS creation/reasoning modules.

## Ownership boundary

The module owns:

- graph node and link domain models
- SQLite persistence under `data/mindmap/mind_map.sqlite3`
- validation and graph mutations
- source references back to chats, sheets, materials, memory, and other modules
- search and bounded local-neighborhood retrieval
- JSON import/export
- graph-change subscriptions and real, ordered ProcessEvent operation traces with generic summaries only
- the PyQt6 Mind Map page

The module does **not** decide which information is important enough to create. That future decision belongs to the Creation Module or Inner Brain. External modules must call `MindMapModule.upsert_source_node(...)`; they must not write to the SQLite tables or scene items directly. The GUI calls Core wrappers only; Core constructs and registers the module as `mind_map`.

## Process event safety

Node and link mutations emit only real operation boundaries: start, saved/deleted result, and exactly one completed or failed terminal event. Event titles and summaries never include node/link titles, graph content, evidence, metadata, raw user-supplied validation errors, backend exception text, or hidden reasoning.

## Persistence and notification safety

`replace_graph=True` imports validate every node and link before one repository transaction clears or writes anything. A malformed record, invalid endpoint, duplicate import node ID, or SQLite write failure rolls back the entire import and retains the previous graph. The SQLite database path is restricted to a relative path contained within the configured project root.

Core graph subscriptions are invalidation notices, not graph transport: they include only event type, entity type, entity ID, graph ID, and timestamp. The GUI refreshes through `Core.get_mind_map_snapshot()` after a notice, so titles, descriptions, content, evidence, source locators, and metadata never cross the public notification boundary.

The PyQt page uses QThread workers for Core graph reads, mutations, JSON import/export, search, and layout persistence. Controls are disabled while work runs, then recover after either success or failure; scene changes are made only by GUI-thread slots. Snapshot refreshes reconcile existing `QGraphicsItem` objects by identifier rather than clearing and rebuilding the scene.

## Workspace interaction

The PyQt6 workspace follows the legacy dark presentation: title, subtitle, framed Mind Map/Graph Space/Context panels, grouped Nodes/Actions tabs, and Context/Node Details tabs. Type colour, importance, confidence, link relevance, selected state, hover state, pin state, and central state determine visual prominence. The force layout is a deterministic in-memory projection; only explicit layout, drag, pin, central, and editing actions persist through Core workers. Pin and central state are narrow node metadata fields (`mindmap_pinned` and `mindmap_central`) rather than a second persistence mechanism.

Visual force motion uses a 33 ms timer only while a changed small graph is moving. It stops after stable motion or a fixed tick bound and never persists timer positions. Live simulation is limited to 120 nodes; explicit synchronous force layout is limited to 80 nodes so its quadratic work cannot stall the GUI. Larger graphs retain their stored positions until a future background layout engine is available.

The prior application's direct source-file opening, filesystem-derived previews, and source-file editing are intentionally excluded. The Mind Map has no direct disk/source-file access: stored node fields are the only context shown by the GUI.

## Main files

- `models.py` — framework-independent graph vocabulary.
- `repository.py` — local SQLite schema and persistence.
- `service.py` — validation, operations, retrieval, events, import/export.
- `mind_map_module.py` — stable facade registered in Core.
- `gui/items.py` — visual node and link objects.
- `gui/view.py` — Mind Map workspace that calls Core only.

## Data model

Nodes currently store type, title, description, content, importance, confidence, status, position, position lock, optional source reference, JSON metadata, and timestamps.

Links currently store source/target, relationship type, label, strength, confidence, permanence, evidence, temporary/expiry fields, decay rate, reward/punishment placeholders, usage count, optional source reference, JSON metadata, and timestamps.

Advanced relevance fields are persisted now but V1 does not yet perform automatic reward propagation, decay, clustering, or autonomous graph cleanup.

## Integration example

A future Chat Registry adapter can create or refresh one stable chat node without depending on graph storage internals:

```python
core.upsert_mind_map_source_node(
    source_type="chat",
    source_id=chat.chat_id,
    title=chat.title,
    node_type="chat",
    description=chat.description,
    metadata={"importance": chat.importance, "tags": chat.tags},
)
```

Repeated calls update the same node because `(graph_id, source_type, source_id)` is unique.
