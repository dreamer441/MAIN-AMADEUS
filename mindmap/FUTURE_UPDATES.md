# Mind Map Future Updates

## Immediate

- Consider a compact visual treatment for stored chat analysis metadata after node-detail usability is evaluated.
- Validate the reconstructed interface on Windows at several graph sizes and tune spacing, label density, and panel proportions from real use.
- Add direct drag-to-connect handles and a lightweight relationship creation overlay.
- Add a source-sync status indicator for chat/sheet/material nodes.
- Add optional chat import modes: metadata only, structured summary, or selected message range.
- Add undo/redo transaction history.
- Add archive/restore support before expanding destructive graph/source operations.
- Add projection visibility and filtering controls for Canvas-backed nodes and links after the automatic Canvas source projection is validated.
- Add read-only `Mind Map` Canvas projection visibility, freshness status, and filtering without introducing Canvas-side source editing or deletion.

## Graph Curator intelligence

- Add a specialized Graph Curator submodule with its own prompt and model routing.
- Convert chats into structured summaries, decisions, tasks, requirements, risks, questions, and evidence-backed relationships.
- Use a proposal layer between LLM output and graph mutations.
- Allow safe metadata/tag proposals automatically; require review for merges, major links, importance changes, and destructive operations.
- Invoke the curator manually first, then through Creation Mode, Drift Mode, and controlled Chat-model requests.

## Retrieval and organization

- Add semantic search while preserving explicit source and relationship evidence.
- Add local, deep, and cluster retrieval modes.
- Add duplicate detection, contradiction proposals, cluster summaries, and knowledge-gap detection.
- Add relevance activation, reward/punishment updates, temporary-link decay, and importance propagation only after their real update logic is implemented.
- Add collapsible containers, multiple graph workspaces, cluster views, and background layout for large graphs.

## Guardrails

- LLM output must never write directly to SQLite.
- Do not automatically delete nodes or evidence based only on scores.
- Keep visual physics transient and service storage authoritative.
- Keep source navigation in MainWindow or owning adapters, never inside storage or graph item classes.
- Keep Inner Brain reasoning, Graph Curator proposals, and deterministic graph storage as separate responsibilities.

## Workspace synchronization follow-ups

- Add a real Materials creation/import API before making `material` nodes workspace-backed.
- Add configurable synchronization policy for global sheets and global memory across multiple chat nodes.
- Add a per-delete choice between delete source, detach graph node, archive source, and cancel; current Mind Map deletion defaults to deleting the represented source object.
- Define optional cascade policy for deleting a Chat node and its separately stored Sheets, Comments, Memories, Materials, and derived graph nodes.
- Add exact source selection for Memory nodes and richer Comment targeting from Mind Map.
- Add optional retroactive import of existing chat sheets, comments, memory, materials, and selected message ranges.
- Add context-budget prioritization when many direct nodes are linked to one chat.
- Add multi-hop context policies separately from default direct-neighbor injection.

## Core ownership cleanup — 2026-09-12

- Extend workspace source synchronization through workspace_integration public APIs rather than importing other module internals into Mind Map.
## Code polish - 2026-09-14

- Keep future form changes in the dialog owner and navigation/drawing behavior in the surface. Shared form helpers must preserve existing widget defaults and validation.
## Drag responsiveness follow-up - 2026-09-15

- Preserve gesture priority over physics and snapshot refreshes when extending live layouts. Keep queued position persistence through Core and verify slow/failing storage plus window shutdown.
