# Canvas Mind Map Projection Design

## Purpose

Project Canvas text blocks and connectors into the Mind Map as source-backed
objects. Canvas blocks appear as rectangular Mind Map nodes, while existing
chat nodes remain circular. Canvas and Mind Map deletions stay synchronized
for these Canvas-owned records.

## Ownership

Canvas remains the authority for Canvas block content, position, title,
metadata, and connector semantics. Mind Map remains the graph relationship
view. The synchronization bridge translates public Canvas and Mind Map APIs;
neither GUI accesses the other's persistence directly.

This phase does not create Canvas objects from manual Mind Map nodes or modify
Canvas source content from Mind Map editing. It only projects Canvas creation
and updates, plus deletion in either direction.

## Source Mapping

Each `CanvasTextBlock` has one Mind Map source node:

- `source_type`: `canvas_block`
- `source_id`: the Canvas `object_id`
- `node_type`: `canvas`
- title, content, and position: copied from the Canvas block

Each `CanvasConnector` has one Mind Map source link:

- `source_type`: `canvas_connector`
- `source_id`: the Canvas `connector_id`
- endpoints: projected Mind Map nodes for the Canvas source and target block
- link type, label, comment/evidence, and metadata: copied from the Canvas
  connector where the graph model supports those fields

The bridge must find source-backed records by these stable IDs before creating
new graph records, making projection idempotent.

## Synchronization

Core coordinates Canvas mutations with the workspace-sync bridge:

- Creating or updating a Canvas block upserts its projected graph node.
- Creating or updating a Canvas connector upserts its projected graph link.
- Deleting Canvas blocks removes their projected graph nodes and all graph
  links sourced from their deleted Canvas connectors.
- Deleting Canvas connectors removes only their projected graph links.
- Deleting a `canvas_block` Mind Map node deletes its Canvas block; Canvas's
  existing cascade deletes attached connectors, and the bridge removes their
  graph links.
- Deleting a `canvas_connector` Mind Map link deletes its Canvas connector.

Deletion handlers must distinguish the initiating side and suppress the
matching reverse removal when the source record is already absent. This avoids
recursive delete loops while leaving other source-backed graph types unchanged.

## Rendering

Mind Map item rendering chooses shape from node ownership:

- chat-backed nodes remain circles;
- Canvas-backed nodes render as rectangles;
- existing non-Canvas nodes retain their current rendering.

Shape is a view concern only. The graph model continues to use `node_type` and
source references rather than persisting GUI-specific geometry.

## Error Handling

- A connector is projected only when both Canvas endpoint blocks have verified
  graph nodes; the bridge first ensures those projections.
- A missing Canvas record during Mind Map deletion is treated as already
  synchronized rather than an error.
- A missing graph record during Canvas deletion is treated as already removed.
- Unsupported source types keep their existing Mind Map deletion behavior.

## Testing

Tests will verify block and connector projection, idempotent updates, Canvas
delete cleanup, Mind Map node-to-block deletion including connector cascade,
Mind Map link-to-connector deletion, and rectangular Canvas node rendering
without changing chat-node circles.

## Non-Goals

- Reverse creation of Canvas blocks from arbitrary Mind Map nodes.
- Editing Canvas content through Mind Map node editing.
- Projecting chat, sheets, comments, or memory as Canvas blocks.
- Synchronizing Canvas workspace deletion with Mind Map graph deletion.
