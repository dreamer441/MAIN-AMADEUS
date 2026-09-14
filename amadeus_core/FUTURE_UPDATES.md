# AMADEUS Core - Future Updates

## Planned improvements

- Add stronger typed response objects instead of plain dictionaries.
- Add clearer module health checks at startup.
- Add safer fallback behavior when optional modules fail.
- Add richer safe trace metadata for routing decisions without including request text.
- Add tests around routing order so exact file requests stay annotation-only and do not fall through to normal LLM chat.
- Add typed chat-management results/errors instead of generic exceptions.
- Consider a Flow-specific Inner Brain advisory route only after it can reuse Flow's explicit command and safe context contracts without changing Flow persistence.
- Consider durable, user-visible pending-action recovery only after an explicit restart and permission design; current approvals intentionally expire with the process.
- Keep shared creation scope defaults in Creation's request service; freeze them in PermissionGuard before approval.
- Keep Habit Tracker pending actions limited to typed owner API fields; do not
  route arbitrary SQL, paths, or LLM-generated identifiers through Core.
- Keep natural Habit Tracker parsing and validation in Flow's dedicated request
  boundary; Core must only register and dispatch typed pending-action fields after approval.

## Boundary

Do not add memory, autonomy, file editing, Mind Map storage/layout, or reasoning implementation directly into Core. Core should stay a coordinator.

## Future Core Routing Improvements

- Add a formal `CoreResponse` dataclass instead of plain dictionaries once payload shapes stabilize.
- Add panel context routing for future `[panel]` and `[current][last_file]` annotations.
- Keep normal chat focused on summaries/explanations while exact tools use explicit annotations.
- Add optional per-chat mode/profile routing later, but keep profile logic outside Core.

## Flow Chat Future Updates

- Add explicit user-selected dedicated-chat retrieval only after its permission and content boundaries are designed.
- Add token-aware Flow history trimming when a shared prompt budget exists.
- Keep future Flow persistence changes transactional at the complete user/AMADEUS exchange boundary.
- Do not expand Flow's Layer 1 registry beyond metadata-only fields without an explicit permission and content-boundary design.

## Future Multi-Chat Improvements

- Add per-chat instruction/profile metadata after the base selector is stable.
- Add chat archive/restore instead of only delete.
- Add migration tests for old single-chat storage.

## Memory/Core Future Updates

- Add memory delete/update routing after Memory Module V1 is stable.
- Add permission checks before any future autonomous memory saving.
- Add richer trace events for memory counts, scope, and panel updates.
- Add Creation Module UI only with a safe registered-source list and explicit per-proposal approval controls.


## Chat Workspace Future Updates

- Add Core routes for chat rename and summary refresh when GUI workflows need them.
- Add `[current]` routing after visible message numbers are stable.
- Add staged callable chat retrieval only after summaries exist and remain separate from active memory.

## Future Panel Context Routing

- [ ] Add safe support for `[panel]` annotation once GUI can provide current visible panel context through a controlled interface.
- [ ] Keep panel context explicit and user-requested; do not automatically inject right-panel data into every prompt.

## Callable Context Roadmap

- [x] Add first callable context route through `[sheet]`.
- [x] Add `[export][chat][message range]` callable context.
- [ ] Add `[panel]` callable context.
- [ ] Add `[current][message number]` callable context.
- [x] Group selected-context conversation execution in Chat Workspace, including Mind Map retrieval.
- [x] Add bounded explicit `[mindmap]` callable retrieval through the injected Mind Map facade.

## Materials Routing Future

- [ ] Add typed material action results once material metadata expands beyond text files and exports.
- [ ] Add unified provenance details to traces for explicit material requests.

## Phase 2 Boundary Follow-up

- [x] Remove inactive legacy callable sheet/export helper bodies from Core; test the injected owner workflows.
- [x] Extract application composition and feature execution; retain `core_coordinator.py` as explicit routing and the lightweight `core.py` public shell.

## Export Routing Future

- [ ] Add richer trace events for export file writing and range selection.
- [ ] Support export references inside future `[current]` / `[panel]` annotation flows.

## Export / Callable Context Future Work

- [x] Lock export prompt scope to selected exported messages.
- [ ] Add a generic callable-context priority system for `[sheet]`, `[export]`, future `[panel]`, and future `[current]`.
- [ ] Add trace inspection for exact callable context size and selected source references.
- Add typed annotation-block result provenance and side-panel aggregation when multiple blocks update different panels.
- Add typed selected-file context provenance if multiple future callable sources need composition rules.

## Side Ask / Comments Future

- [ ] Link new Side Ask chats back to their source chat/message selection.
- [ ] Add Side Ask-to-sheet action.
- [ ] Add Side Ask-to-memory suggestion after user confirmation.
- [ ] Use exact message refs after `[current]` exists.

## Mind Map synchronization follow-ups

- Add transaction compensation when a future cross-module operation fails after one owner has already persisted.
- Add Materials and richer Memory source adapters after their public create/update/delete contracts are complete.

## Canvas Routing Follow-ups

- [x] Expose explicit Canvas document, workspace, block and connector routes through `core.canvas`.
- Keep viewport context assembly, delta tracking, and Canvas LLM requests inside Canvas services rather than growing Canvas-specific logic inside Core.
- Keep future Canvas projection controls and policy in the Canvas/Mind Map bridge instead of writing graph storage from Core.
- Keep the read-only Mind Map-to-Canvas projection reconciliation in the Canvas/Mind Map bridge; do not add Core routes that permit managed projection edits or deletes.

## Module Metadata Routing Follow-Up

- Add metadata-routing refinements only if they preserve the existing fixed-file reader boundary and Flow exclusion.

## Core ownership cleanup — 2026-09-12

- Ownership direction: Keep new operations as explicit owner routes; retire compatibility accessors only after consumers migrate.
