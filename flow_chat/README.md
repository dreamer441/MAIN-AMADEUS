# Flow Chat

`flow_chat` owns the persistent Flow home conversation. It is separate from the dedicated chats managed through the Chats page and reuses Core's public Flow route rather than changing normal chat behavior.

Flow history is stored locally under `data/flow_chat/`; dedicated chats remain under `data/chats/`. A successful Flow user/AMADEUS exchange is written together, while a failed request adds no partial exchange.

## Context Boundary

Flow constructs two separate context layers for each request:

- Layer 0: bounded recent Flow history.
- Layer 1: `[AVAILABLE DEDICATED CHATS]` registry metadata.

Layer 1 contains only `chat_id`, title, description, priority, purpose, and scope. It never loads or injects dedicated-chat message bodies. Scope is descriptive V1 metadata only and does not cause automatic cross-chat retrieval. The metadata is read from the current dedicated-chat store for each Flow context build, so created, renamed or otherwise metadata-updated, and deleted chats are reflected without Flow maintaining a copy.

## Events

Flow uses the shared Process Monitor event lifecycle provided by Core. Events report safe execution boundaries and can be delivered live to the GUI as well as returned in the final response payload. They are diagnostic information, not hidden reasoning.
