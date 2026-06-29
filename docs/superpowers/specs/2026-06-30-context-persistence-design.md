# Project Context And Chat Persistence Design

Date: 2026-06-30

## Goal

Let AMADEUS use read-only project file context during normal chat when the user asks about files/modules, and persist the current chat so the GUI can resume it.

## Scope

Included:

- Core detects normal project/file/module questions.
- Core builds read-only project context through `ProjectFileReader`.
- Chat receives context from Core and sends it to the LLM.
- Storage saves user and AMADEUS messages to local JSONL.
- GUI loads recent chat history through Core at startup.

Excluded:

- File editing.
- Deep automatic code scanning.
- Long-term memory.
- Multiple chat sessions.
- Chat search.
- Database storage.

## Architecture

Normal file-aware chat flow:

```text
GUI -> Core -> ProjectFileReader -> Chat -> LLM Client -> Ollama
```

Persistence flow:

```text
Core -> Storage -> data/chats/current_chat.jsonl
GUI -> Core -> Storage -> loaded messages
```

Core coordinates. Chat never reads files directly. GUI never reads storage directly.

## Safety

Project context remains read-only and compact. It includes module docs and top-level Python file names only.

Chat data is local runtime data under `data/chats/` and is ignored by git.
