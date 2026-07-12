# AMADEUS Chat Future Updates

- Streaming responses.
- Better prompt templates.
- Per-chat settings.
- Reasoning-profile aware prompts.
- Message-level metadata for future memory and reflection.
- Optional prompt preview/debug mode through Process Monitor, without exposing hidden reasoning.
- Better separation of system prompt, identity prompt, history prompt, project context, and latest user request.

## Future Chat Context Improvements

- Add explicit support for injected Code Viewer context only when Dato uses a future `[panel]` or `[current][last_file]` annotation.
- Add line-reference-aware explanations after exact file blocks are available as structured context.

## Memory Prompt Future Updates

- Add better rules for resolving memory conflicts.
- Add clearer handling when memory says a topic is private/project-specific.
- Add future `[panel]` support so opened code/memory panel content can be injected on request.


## Current Message Reference Future Updates

- Support `[current][number]` after Annotation Module owns message selection.
- Support generated chat summaries as callable context, not constant active prompt memory.
- Add chat mode/reason behavior only after reasoning profiles and skills define actual differences.

## Callable Context Roadmap

- [x] Add callable context prompt section.
- [ ] Add callable export segments.
- [ ] Add callable panel context.
- [ ] Add callable current-message context.

## Callable Context Future Work

- [ ] Add per-source prompt templates for sheet/export/panel/current contexts instead of one generic callable context block.
- [ ] Add source citations or message-number references in AMADEUS answers when using exported segments.
