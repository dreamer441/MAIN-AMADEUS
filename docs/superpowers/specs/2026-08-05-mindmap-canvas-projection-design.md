# Mind Map Canvas Projection Design

## Purpose

Show source-backed Mind Map content in a dedicated, read-only Canvas workspace.
Chats, sheets, memories, comments, and Canvas blocks become compact Canvas
boxes; their Mind Map relationships become Canvas connectors.

## Managed Workspace

Canvas owns one stable workspace ID, `mindmap_projection`, titled `Mind Map`.
It is created or selected during projection reconciliation. It is separate
from normal editable Canvas workspaces.

## Projection Mapping

Each eligible Mind Map node has one managed Canvas block. Eligible source
types are `chat`, `sheet`, `memory`, `comment`, and `canvas_block`.
The block stores the graph node ID, source reference, and
`mindmap_projection: true` metadata. Its title, content, and graph position
are mirrored from the graph node.

Each Mind Map link whose endpoints both have managed blocks has one managed
Canvas connector. Its metadata stores the graph link ID and
`mindmap_projection: true`; its relation type, label, and evidence mirror the
graph link.

## Synchronization And Ownership

Projection runs after source-node updates, graph link changes, deletions, and
startup reconciliation. Missing projections are created, changed projections
are updated, and stale managed blocks/connectors are removed.

Managed Canvas records are locked and Canvas UI actions refuse their edit or
managed Canvas deletion never deletes a chat, sheet, memory, comment, Canvas
source block, or Mind Map record.

The existing Canvas-to-Mind Map bridge ignores records marked
`mindmap_projection: true`, preventing event feedback loops. Normal editable
Canvas workspaces and their Canvas-to-Mind Map behavior are unchanged.

## Rendering

Canvas-backed nodes in Mind Map use a compact `84 x 40` rounded rectangle,
replacing the current oversized rectangle. Chat nodes remain circular.

## Tests

Tests cover managed workspace reconciliation, every eligible source type,
connector projection, source/link removal, projection event-loop prevention,
and Canvas rejection of managed edit/delete requests. Rendering tests verify
the compact rectangle and unchanged circular chat geometry.

## Non-Goals

- Editing or deleting AMADEUS sources through the managed Canvas workspace.
- Creating new sources from projection Canvas blocks.
- Projecting graph-only nodes without an eligible source reference.
