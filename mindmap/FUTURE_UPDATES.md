# Mind Map Future Updates

## Near-term

- Add undo/redo transaction history.
- Add node grouping, containers, collapse/expand, and multiple graph workspaces.
- Add richer layout engines while preserving positions locked either manually or by `mindmap_pinned` metadata.
- Add a background or progressively computed layout engine for graphs above the current 80-node synchronous layout cap.
- Add link endpoint handles and direct drag-to-connect interaction.
- Add source-opening adapters so a chat/sheet/material node can jump to its original object.
- Any future source-opening adapter must be Core-mediated and permission-guarded; the Mind Map GUI must not read, edit, or open source paths directly.
- Keep source metadata adapters Core-mediated; source modules must use `upsert_mind_map_source_node` rather than SQLite.
- Add controlled Chat Registry synchronization after Chat Registry V2 stabilizes.
- Add comments on nodes and links through the Comments Module.
- Add broader batch graph creation and relationship operations for large Creation Module updates.
- Add database migrations and backup/restore controls in the GUI.

## Retrieval and intelligence

- Three-layer retrieval: local, deep traversal, and cluster retrieval.
- Semantic search and duplicate-node detection.
- Evidence inspection and contradiction detection.
- Relevance scoring, link activation counts, reward/punishment updates, and importance propagation.
- Temporary inference links with expiry and decay.
- Cluster creation and topic-level summaries.
- Knowledge-gap detection.
- Creation Module proposals with confirmation and visible process events.

## Guardrails

- Do not let LLM output write directly to SQLite.
- Do not automatically delete nodes based only on a low score.
- Do not treat stored reward/decay fields as implemented intelligence until their real update logic exists.
- Keep Inner Brain reasoning separate from graph storage and visualization.
- Preserve atomic import semantics: future bulk importers must validate their source schema before entering the repository transaction and must not publish graph data in invalidation notifications.
- Keep long-running graph I/O in Qt workers; scene and widget updates must remain on the GUI thread.
