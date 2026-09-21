# Chat Workspace Features

- Inner Brain failures are visible in Process Monitor while ordinary Chat continues. Failed/incomplete or empty-chat metadata refreshes preserve the previous successful analysis and report an error through the existing GUI status path.

- Owns dedicated-chat request execution, selected-context conversations, lifecycle, metadata, documents and exchange persistence. Chat generation remains in amadeus_chat and context selection in context_builder.
- conversation.py executes requests; selected_context.py runs explicit context conversations; lifecycle.py manages chats; metadata.py handles analysis and exports; documents.py coordinates scoped documents; exchanges.py persists through Storage.
