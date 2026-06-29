# AMADEUS Core Features

- Creates a module registry.
- Registers the Chat module.
- Routes user messages to Chat.
- Checks structured annotations before normal chat.
- Routes `[file]` annotations to the Annotation Module.
- Supplies read-only project context to Chat when normal messages ask about project files or modules.
- Persists user and AMADEUS chat messages through Storage.
