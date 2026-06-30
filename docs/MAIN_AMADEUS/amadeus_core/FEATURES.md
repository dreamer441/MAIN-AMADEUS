# AMADEUS Core Features

- Creates a module registry.
- Registers the Chat module.
- Registers the Identity module.
- Routes user messages to Chat.
- Checks structured annotations before normal chat.
- Routes `[file]` annotations to the Annotation Module.
- Routes `[identity]` annotations to the Identity Module.
- Supplies AMADEUS identity context to Chat for every normal message.
- Supplies a stronger project identity prompt when normal messages ask about project files or modules.
- Supplies read-only project context to Chat when normal messages ask about project files or modules.
- Persists user and AMADEUS chat messages through Storage.
