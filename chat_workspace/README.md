# Chat Workspace

Owns dedicated-chat request execution, selected-context conversations, lifecycle, metadata, documents and exchange persistence. Chat generation remains in amadeus_chat and context selection in context_builder.

## Files

conversation.py executes requests; selected_context.py runs explicit context conversations; lifecycle.py manages chats; metadata.py handles analysis and exports; documents.py coordinates scoped documents; exchanges.py persists through Storage.

See `docs/ARCHITECTURE.md` for cross-module ownership.
