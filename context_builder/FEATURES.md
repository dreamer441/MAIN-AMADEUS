# Context Builder Features

- Builds recent conversation context from persisted chat history.
- Keeps recent context compact so local models do not lose the current user message.
- Selects read-only AMADEUS project overview when the user asks about files, modules, documentation, or structure.
- Returns a simple context bundle that Core can pass to Chat.
