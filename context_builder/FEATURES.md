# Context Builder - Current Features

## Purpose
Context Builder chooses what context enters a normal chat prompt. This prevents Core and Chat from directly owning history/file-context policy.

## Implemented features

- Loads recent persisted conversation messages for continuity.
- Uses the active chat selected in Storage, so switching chats changes the conversation history AMADEUS sees.
- Trims history to a small character budget.
- Adds read-only project overview context when the user appears to ask about project structure.
- Keeps project context compact and verified.
- Leaves exact file reads, exact line reads, and exact line counts to Project File Reader / `[file]` annotation so normal chat does not guess them.

## Boundary

Context Builder selects context; it does not answer the user directly, switch chats, edit files, or manage long-term memory.

## Memory Context Injection

- Context Builder now injects explicit saved global memory into every normal chat prompt.
- Context Builder injects current-chat memory only into the active chat.
- Memory context is separate from recent chat history and project overview context.


## Chat Workspace Context

- Injects active chat title/description into normal chat prompts.
- Keeps chat workspace context separate from global memory, chat memory, recent conversation, and project overview.
- Recent conversation context now includes visible message numbers, preparing future `[current]` annotations.

## Shared Process Events

- `build_for_message()` accepts an optional `TraceLogger` and reports genuine context start/completion boundaries.
- Completion reports only selected context type names (`recent_conversation`, `project_overview`, `memory`, and `chat_workspace`), never context values.
