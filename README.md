# AMADEUS

AMADEUS is a local-first personal AI project designed to grow as a clean modular desktop system.

This first rebuild is intentionally small. It creates a working shell with:

- AMADEUS Core
- AMADEUS Chat module
- AMADEUS Identity module
- AMADEUS Process Monitor / Trace module
- AMADEUS PyQt6 GUI
- Ollama local LLM client
- Placeholder folders for future modules

## Current Behavior

The app opens a desktop window. You can type a message, press Send or Enter, and AMADEUS routes it through Core to the Chat module. The top bar has a simple chat selector with New Chat and Delete Chat controls. The right panel has Process Monitor and Code Viewer tabs. The Process Monitor shows real execution events from the latest request, such as input received, annotation check, routing decision, LLM call status, errors, and output ready.

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

This version includes a simple local Ollama LLM connection, the AMADEUS Identity Module, the AMADEUS Process Monitor, read-only `[identity]` annotations, deterministic read-only `[file]` annotations, a right-side Code Viewer, multiline input, guided annotation suggestions, and first multi-chat support. It does not include real reasoning, memory, skills, mind map, advanced permissions, streaming responses, or model picker UI yet.

## Annotations

Annotations are structured commands that start a message with brackets.

```text
[file]
[file][amadeus_core]
[file][identity_module]
[file][identity_module][identity_charter.py]
[identity]
[identity][charter]
```

`[file]` lists available module folders. `[file][module_name]` lists verified direct folders/files for that module. `[file][module_name][folder]` lists a subfolder. `[file][module_name][file.py]` opens exact safe text content in the right-side Code Viewer instead of dumping the file into chat.

`[identity]` shows the active Identity Module status. `[identity][charter]` shows the full AMADEUS Identity Charter. `[identity][prompt]` and `[identity][project]` show the prompts Core can inject into Chat.

AMADEUS can also use compact read-only project overview context during normal chat when you ask for summaries or explanations about modules. Exact file content and exact folder/file listings should use `[file]` so they come from verified filesystem tools instead of LLM guessing. Identity context is injected into every normal chat message.

## Process Monitor

The Process Monitor shows real execution events from code. It is not hidden thinking and must not be used to invent private reasoning.

Current trace examples include:

```text
[Input Received]
Message received from GUI.

[Annotation Check]
Checking if message starts with a registered annotation pattern.

[Routing Decision]
No annotation detected. Routing to chat module.

[LLM Client]
Sending message to the configured Ollama model.

[Output Ready]
Response returned to GUI.
```

## Chat Persistence

AMADEUS saves local chats under:

```text
data/chats/
```

The active chat list is tracked in:

```text
data/chats/chats_index.json
```

Each conversation has its own JSONL file. The GUI loads the active chat on startup and reloads history when you switch chats. Chat history is local runtime data and is ignored by git.

## Development Workflow Rules

AMADEUS now follows two required development-maintenance rules:

1. When a current or future feature is discussed or implemented, update the affected module docs, especially `FEATURES.md` and `FUTURE_UPDATES.md`.
2. Code must include useful comments explaining architecture, ownership, data flow, and safety boundaries so Dato can read the project naturally.

The detailed rule file is:

```text
docs/DEVELOPMENT_WORKFLOW_RULES.md
```

## Current UI / File Access Patch

- Normal chat is now for conversation, summaries, and explanations.
- Exact file access should use `[file]` annotation commands.
- The right panel now has Process Monitor and Code Viewer tabs.
- `[file][module][file.py]` opens exact read-only file content in Code Viewer instead of dumping code into the chat.
- The message box is multiline: Enter sends, Shift+Enter inserts a newline.
- Typing `/` starts the first guided annotation suggestion flow.

## Multi-Chat v1

- Use the top chat selector to switch between local conversations.
- `New Chat` opens a dialog for title and optional description, creates the workspace, and switches to it.
- `Delete Chat` asks for confirmation and removes the selected chat history file.
- Chat switching also clears the right-side Process Monitor/Code Viewer state so old panel context is not confused with the newly selected chat.
- Visible messages are numbered as `[1]`, `[2]`, `[3]`, preparing future `[current][number]` context injection.
- The active chat title/description appears in the Memory panel as current chat context.
- While AMADEUS is answering, chat switching is disabled so the response cannot be saved into the wrong chat.

## Latest Patch: Chat Workspace V2

- Added visible chat-local message numbers in the main conversation view.
- New Chat now opens a creation dialog with Title and Description.
- Chat descriptions are stored in chat metadata and shown in the right-side Memory panel as current chat context.
- Context Builder injects the active chat title/description into normal chat prompts.
- Added root-level `AMADEUS_CHANGELOG.md` and `AMADEUS_FUTURE_IMPLEMENTATIONS.md` so global project progress is tracked in one place in addition to per-module docs.
- Chat reasons/modes, generated summaries, and staged metadata retrieval are documented for future work, but not implemented yet.

## Side Panel Foundation

AMADEUS now has a dedicated `side_panel` module and a reusable GUI `RightPanelWidget`.

The right panel currently displays:

- Process Monitor
- Code Viewer
- Memory

The side panel is a display/state foundation only. It does not own file reading, memory storage, or trace generation. Those responsibilities stay in their own modules. This prepares AMADEUS for future tabs such as Sheets, Materials, Diff Viewer, and `[panel]` context injection without turning `main_window.py` into a giant file.

## Sheets V1 and Materials Foundation

AMADEUS now has editable sheets in the right-side panel.

Sheets are scoped as either:

- `chat`: visible only in the current chat workspace.
- `global`: visible across chats.

Use `[sheet]` to open sheets, and use `[sheet][scope][title] prompt` to inject one sheet into a normal AMADEUS response as callable context.

The right panel also now includes a Materials tab foundation for future chat exports, PDFs, text materials, and image references. Chat export is planned to support selected message ranges such as `[export][chat name][4-6]`.

## Chat Export V1

AMADEUS now supports exported chats as callable Materials references.

Use:

```text
[export]
```

to export the current chat into TXT, Markdown, and JSON. Use:

```text
[export][Chat Title][4-6]
```

to open a numbered message segment in the Materials panel. Add prompt text after the annotation to inject only that segment as callable context for one answer.

Exports are not active memory. They are stored references that AMADEUS can use only when Dato explicitly calls them.

## Patch Note: Side Ask V1 + Simple Comments

The right panel now includes **Side Ask** and **Comments** tabs. Side Ask is a temporary secondary question flow that can use selected chat text as context, then optionally save its Q&A into the current chat or create a new chat from it. Comments let Dato select chat text and attach a simple note without mixing it with memory, reward, or importance yet.
