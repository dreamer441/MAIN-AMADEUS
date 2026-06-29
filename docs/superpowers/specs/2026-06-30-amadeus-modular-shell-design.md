# AMADEUS Modular Shell Design

Date: 2026-06-30

## Goal

Rebuild `D:\MAIN_AMADEUS` as a clean first version of AMADEUS: a local-first, modular desktop shell with a working GUI feedback loop.

This version must open a desktop window, accept a user message, route the message through Core, execute placeholder chat logic inside the Chat module, and display the response.

## Scope

Included in this first rebuild:

- AMADEUS Core shell.
- PyQt6 desktop GUI.
- Simple AMADEUS Chat module.
- Placeholder folders for future modules.
- Documentation inside every module folder.
- Root documentation explaining architecture and first steps.

Excluded from this first rebuild:

- Advanced reasoning.
- Memory or database storage.
- Mind map features.
- Skills execution.
- Ollama or cloud LLM connections.
- File editing tools.
- Web access.
- Complex permissions.
- A large module loader/plugin system.

## Architecture

AMADEUS will use a simple modular boundary from the beginning:

- `main.py` starts the app and wires Core into the GUI.
- `amadeus_core` coordinates modules and routes user input.
- `amadeus_chat` executes chat behavior.
- `amadeus_gui` owns the desktop interface.
- Placeholder module folders reserve future system boundaries.

Core routes. Modules execute. The GUI talks to Core, not directly to Chat.

## Components

### main.py

Responsibilities:

- Create `AmadeusCore`.
- Create the PyQt6 application.
- Create `AmadeusMainWindow` and pass Core into it.
- Start the GUI event loop.

Must not:

- Contain module logic.
- Contain chat behavior.
- Contain future AI features.

### amadeus_core/core.py

Responsibilities:

- Create a `ModuleRegistry`.
- Register the `AmadeusChatModule` under the name `chat`.
- Provide `handle_user_message(message: str) -> str`.
- Route all current user messages to the chat module.

Must not:

- Generate chat responses itself.
- Directly control future reasoning, memory, skills, or UI internals.

### amadeus_core/module_registry.py

Responsibilities:

- Register modules by name.
- Retrieve modules by name.
- List registered module names.

Must not:

- Execute module logic.
- Know module internals beyond the registered object.

### amadeus_chat/chat_module.py

Responsibilities:

- Define `AmadeusChatModule`.
- Provide `handle_message(message: str) -> str`.
- Return `AMADEUS received: <message>` for now.

Must not:

- Call an LLM yet.
- Store memory yet.
- Perform reasoning yet.

### amadeus_gui/main_window.py

Responsibilities:

- Create the AMADEUS desktop window.
- Show chat history.
- Provide user input and a Send button.
- Send on Enter.
- Call `core.handle_user_message()`.
- Display both user and AMADEUS messages.

Must not:

- Call the chat module directly.
- Own business logic beyond GUI event handling.

## GUI Choice

Use PyQt6.

Reason:

- Better long-term desktop foundation than Tkinter.
- More suitable for future panels, sidebars, settings, mind maps, and module views.
- Keeps the app closer to a real expandable desktop application.

Tradeoff:

- Requires installing dependencies with `pip install -r requirements.txt`.

## Project Structure

The rebuild will create this structure:

```text
D:\MAIN_AMADEUS
├── main.py
├── README.md
├── requirements.txt
├── amadeus_core/
├── amadeus_chat/
├── amadeus_gui/
├── reasoning_module/
├── skills/
├── mindmap/
├── storage/
├── llm_client/
├── permissions/
└── docs/
```

Every module-style folder will include:

- `README.md`
- `FEATURES.md`
- `FUTURE_UPDATES.md`

Python package folders will also include `__init__.py`.

## Data Flow

1. User opens the app with `python main.py`.
2. `main.py` creates `AmadeusCore`.
3. `AmadeusCore` registers `AmadeusChatModule` in `ModuleRegistry`.
4. `main.py` creates the PyQt6 GUI and passes Core into it.
5. User types a message and presses Send or Enter.
6. GUI displays `User: <message>`.
7. GUI calls `core.handle_user_message(message)`.
8. Core retrieves the `chat` module from the registry.
9. Core calls `chat.handle_message(message)`.
10. Chat returns `AMADEUS received: <message>`.
11. GUI displays `AMADEUS: AMADEUS received: <message>`.

## Error Handling

- Empty messages will be ignored by the GUI.
- If the chat module is missing, Core returns a clear error string instead of crashing.
- GUI exceptions will not be hidden behind advanced systems in this first version.

## Comments And Documentation

Code comments will use real Python comments with `#` or `##`.

Comments should explain architecture and intent, especially:

- Why Core routes instead of executing chat logic.
- Why GUI calls Core instead of Chat.
- Where future reasoning and LLM integration will connect.

Comments should not explain obvious imports or simple assignments.

## Testing And Verification

Manual verification for this first shell:

1. Install dependencies with `pip install -r requirements.txt` if PyQt6 is not installed.
2. Run `python main.py` or `py -3 main.py` from `D:\MAIN_AMADEUS`.
3. Confirm the AMADEUS window opens.
4. Type a message and press Send.
5. Confirm the history shows the user message and placeholder AMADEUS response.
6. Press Enter in the input field and confirm it sends the message.

## Next Step After This Rebuild

The next logical step is to define a formal module interface contract. That should specify how future modules register capabilities, expose commands, report status, and request permission-protected actions.

No advanced AI behavior should be added until the shell remains stable and understandable.
