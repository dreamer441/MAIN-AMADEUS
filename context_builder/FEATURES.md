# Context Builder - Current Features

## Purpose

Context Builder chooses what context enters a normal chat prompt. This prevents Core and Chat from directly owning history/file-context policy.

## Implemented features

* Loads recent persisted conversation messages for continuity.
* Uses the active chat selected in Storage, so switching chats changes the conversation history AMADEUS sees.
* Trims history to a small character budget.
* Adds read-only project overview context when the user appears to ask about project structure.
* Keeps project context compact and verified.
* Leaves exact file reads, exact line reads, and exact line counts to Project File Reader / `\\\[file]` annotation so normal chat does not guess them.

## Boundary

Context Builder selects context; it does not answer the user directly, switch chats, edit files, or manage long-term memory.

## Memory Context Injection

* Context Builder now injects explicit saved global memory into every normal chat prompt.
* Context Builder injects current-chat memory only into the active chat.
* Memory context is separate from recent chat history and project overview context.



## Chat Workspace Context

* Injects active chat title/description into normal chat prompts.
* Keeps chat workspace context separate from global memory, chat memory, recent conversation, and project overview.
* Recent conversation context now includes visible message numbers, preparing future `\\\[current]` annotations.

## Shared Process Events

* `build\\\_for\\\_message()` accepts an optional `TraceLogger` and reports genuine context start/completion boundaries.
* Reports each source only after it was actually loaded or selected: recent history,
project overview, explicit memory, and active chat workspace metadata. No context
values are included in events.

## Linked graph context

* Normal Chat context may include bounded direct Mind Map neighbors explicitly linked to the active chat.
* Per-link `inject\\\_into\\\_chat` metadata allows a relationship to remain visible without entering the LLM prompt.
* Linked graph records use explicit literal fields and content delimiters instead of one ambiguous generated-looking context sentence.
* Linked records tell Chat to keep objects separate, report empty fields honestly, and prefer exact stored values over older assistant claims.


## Core ownership cleanup — 2026-09-12

- Implemented: Bounded inferred read selection lives in InferredContextAdvisor. Literal retrieved Mind Map records are formatted here, separately from conversation execution.

## Advisory retrieval repair — 2026-09-21

- Inferred sheet, export, and Mind Map hints return real, bounded inventories through public read APIs instead of UI-handler success text. No inferred export can create or refresh export files.
- Flow lists global sheets only; dedicated Chat lists its own and global sheets. Export and graph hints expose titles/counts/types, never stored bodies. Exact content still requires explicit selection.
- Invalid model targets do not broaden module metadata access. Advisory failure is visible in safe Process Monitor events and does not prevent the primary answer.
