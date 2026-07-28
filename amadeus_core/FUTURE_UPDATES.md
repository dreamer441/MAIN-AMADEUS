# AMADEUS Core - Future Updates

## Planned improvements

- Add stronger typed response objects instead of plain dictionaries.
- Add clearer module health checks at startup.
- Add safer fallback behavior when optional modules fail.
- Add richer safe trace metadata for routing decisions without including request text.
- Add tests around routing order so exact file requests stay annotation-only and do not fall through to normal LLM chat.
- Add typed chat-management results/errors instead of generic exceptions.

## Boundary

Do not add memory, autonomy, file editing, mind map, or reasoning implementation directly into Core. Core should stay a coordinator.

## Future Core Routing Improvements

- Add a formal `CoreResponse` dataclass instead of plain dictionaries once payload shapes stabilize.
- Add panel context routing for future `[panel]` and `[current][last_file]` annotations.
- Keep normal chat focused on summaries/explanations while exact tools use explicit annotations.
- Add optional per-chat mode/profile routing later, but keep profile logic outside Core.

## Future Multi-Chat Improvements

- Add chat rename support through Storage and GUI.
- Add per-chat instruction/profile metadata after the base selector is stable.
- Add chat archive/restore instead of only delete.
- Add migration tests for old single-chat storage.

## Memory/Core Future Updates

- Add memory delete/update routing after Memory Module V1 is stable.
- Add permission checks before any future autonomous memory saving.
- Add richer trace events for memory counts, scope, and panel updates.


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
- [ ] Add unified callable context service before Mind Map integration.

## Materials Routing Future

- [ ] Add typed material action results once material metadata expands beyond text files and exports.
- [ ] Add unified provenance details to traces for explicit material requests.

## Phase 2 Boundary Follow-up

- [ ] Remove the inactive legacy callable sheet/export helper bodies from Core after the new Annotation Module router has a focused routing test suite.
- [ ] Extract remaining Core feature routes one module at a time; do not combine them into a Core rewrite.

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
