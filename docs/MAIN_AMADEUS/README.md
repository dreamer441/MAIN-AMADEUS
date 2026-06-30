# AMADEUS

AMADEUS is a local-first personal AI project designed to grow as a clean modular desktop system.

This first rebuild is intentionally small. It creates a working shell with:

- AMADEUS Core
- AMADEUS Chat module
- AMADEUS Identity module
- AMADEUS PyQt6 GUI
- Ollama local LLM client
- Placeholder folders for future modules

## Current Behavior

The app opens a desktop window. You can type a message, press Send or Enter, and AMADEUS routes it through Core to the Chat module.

Chat now uses the local Ollama LLM client. The default lightweight model is `llama3.2:latest`.

## How To Run

Install Ollama from:

```text
https://ollama.com
```

Pull the default AMADEUS model if it is not already installed:

```bash
ollama pull llama3.2
```

The heavier `qwen3:32b` model can stay installed for later heavier tasks.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

If Windows does not recognize `python`, try:

```bash
py -3 main.py
```

## Current Scope

This version includes a simple local Ollama LLM connection, the AMADEUS Identity Module, read-only `[identity]` annotations, and read-only `[file]` annotations. It does not include real reasoning, memory, skills, mind map, storage, advanced permissions, streaming responses, or model picker UI yet.

## Annotations

Annotations are structured commands that start a message with brackets.

```text
[file]
[file][amadeus_core]
[identity]
[identity][charter]
```

`[file]` lists available module folders. `[file][module_name]` reads that module's documentation files in a controlled, read-only way.

`[identity]` shows the active Identity Module status. `[identity][charter]` shows the full AMADEUS Identity Charter. `[identity][prompt]` and `[identity][project]` show the prompts Core can inject into Chat.

AMADEUS can also use the same read-only project context during normal chat when you ask about project files, modules, README files, or structure. Identity context is injected into every normal chat message.

## Chat Persistence

AMADEUS saves the current local chat to:

```text
data/chats/current_chat.jsonl
```

The GUI loads recent messages on startup. Chat history is local runtime data and is ignored by git.
