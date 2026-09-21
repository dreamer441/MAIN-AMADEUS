# Context Builder - Future Updates

## Planned improvements

* Add token-aware context limits.
* Add module-specific context packs.
* Add source labels for each injected context section.
* Add safe aggregate context selection metrics only after a privacy review.
* Add stronger detection for when project context is useful.
* Add per-chat instruction/profile context after the multi-chat foundation stabilizes.
* Add future integration with memory and relevance graph once those modules are stable.
* Add `\\\[panel]` and `\\\[current]` context injection later, but only when explicitly requested.

## Important boundary

Do not use Context Builder as a substitute for deterministic file inspection. Exact file content questions should use `\\\[file]` and GUI side panels, not normal LLM guessing.

## Memory Context Future Updates

* Add token-aware memory selection.
* Add recency/importance weighting when Memory Module supports importance.
* Add conflict detection so old memory does not silently override newer corrections.



## Callable Context Future Updates

* Add callable chat summaries as a third retrieval layer after title and description.
* Add selection logic that first scans chat titles, then descriptions, and only retrieves summaries for likely relevant chats.
* Keep active memory and callable memory separate so prompt context stays clean.

## Callable Export Context

* \[x] Support export context injection through Core/callable context path.
* \[ ] Add staged retrieval for exported chats: title -> description -> summary -> exact range.

## Graph context follow-ups

* Add token-aware prioritization, source-type budgets, and user-visible explanations when linked context is truncated.
* Keep multi-hop and semantic retrieval separate from default direct-neighbor context.


## Core ownership cleanup — 2026-09-12

- Ownership direction: Evolve context budgets and typed provider contracts without moving selection back into Core or GUI.

- Keep inferred inventories read-only and separate from display handlers, especially export handlers that write files. Any richer inferred retrieval needs explicit selection and scope contracts first.
