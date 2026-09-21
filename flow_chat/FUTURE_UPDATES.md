# Flow Chat Future Updates

- Add token-aware Flow history trimming when a shared prompt budget is defined.
- Design explicit user-selected dedicated-chat retrieval only after permissions and content boundaries are defined.
- Add relevance ranking for metadata records without loading dedicated-chat bodies.
- Keep any future persistence changes transactional at the full user/AMADEUS exchange boundary.
- Do not treat Flow's current metadata-only registry as dedicated-chat content access.
- Do not operationalize chat scope until explicit selection, permissions, and content boundaries are designed.
- Keep `/review` explicit and read-only; broader intent-to-command routing belongs to a future Second Brain boundary.
- Keep `/create-chat` explicit; Inner Brain creation intent must remain limited to the approved `chat`, `sheet`, and `memory` kinds.
- Keep workspace creation restricted to registered Core approval requests; do not add arbitrary command, filesystem, or model-provided action routing.
- Keep Flow advisory inference constrained to Context Builder's bounded read-only inventories and registered pending actions; do not accept model-provided locators or retrieve dedicated-chat bodies.
- Keep Habit Tracker natural-language aliases bounded and deterministic; do not
  introduce LLM-derived task fields, dates, identifiers, or write actions.
- Keep one-time task default-date behavior and bounded priority phrases inside the
  dedicated Habit request boundary; do not expand it into LLM-derived routing.

## Core ownership cleanup — 2026-09-12

- Ownership direction: Keep Flow-specific execution inside this module and shared creation behavior inside Creation.
