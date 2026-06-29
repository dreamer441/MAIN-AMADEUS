# AMADEUS Modular Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `D:\MAIN_AMADEUS` as a clean modular AMADEUS shell with a PyQt6 GUI, Core routing, and a placeholder Chat module.

**Architecture:** `main.py` wires together Core and GUI. Core owns module registration and routes user messages to the Chat module. GUI owns display/input only and calls Core instead of calling Chat directly.

**Tech Stack:** Python 3, PyQt6, standard library modules only outside PyQt6.

## Global Constraints

- Work in `D:\MAIN_AMADEUS`.
- Use PyQt6 for the desktop GUI.
- Core routes; modules execute.
- GUI calls Core, not Chat directly.
- Chat returns `AMADEUS received: <message>` for now.
- Do not build advanced reasoning yet.
- Do not build memory yet.
- Do not build mind map yet.
- Do not build skills yet.
- Do not connect Ollama yet.
- Do not create a huge complex system.
- Every module-style folder must contain `README.md`, `FEATURES.md`, and `FUTURE_UPDATES.md`.
- Use real Python comments with `#` or `##`; do not use string comments as comments.

---

## File Structure

Create or replace these files:

- `main.py`: process entry point; creates Core, creates PyQt6 app, opens GUI.
- `README.md`: root project overview and run instructions.
- `requirements.txt`: PyQt6 dependency.
- `.gitignore`: ignores caches, venvs, IDE files, logs, and temporary files.
- `amadeus_core/__init__.py`: package marker.
- `amadeus_core/core.py`: `AmadeusCore` coordinator and message router.
- `amadeus_core/module_registry.py`: simple module registry.
- `amadeus_chat/__init__.py`: package marker.
- `amadeus_chat/chat_module.py`: placeholder chat module.
- `amadeus_gui/__init__.py`: package marker.
- `amadeus_gui/main_window.py`: PyQt6 main window.
- `reasoning_module/__init__.py`: placeholder package marker.
- `skills/__init__.py`: placeholder package marker.
- `mindmap/__init__.py`: placeholder package marker.
- `storage/__init__.py`: placeholder package marker.
- `llm_client/__init__.py`: placeholder package marker.
- `permissions/__init__.py`: placeholder package marker.
- Documentation files in each module-style folder: `README.md`, `FEATURES.md`, `FUTURE_UPDATES.md`.
- `docs/ARCHITECTURE.md`: architecture explanation.
- `docs/MODULE_RULES.md`: module rules.
- `docs/FIRST_STEPS.md`: first version explanation and next steps.

Remove obsolete files and folders from the previous Core-only version:

- `run_core.bat`
- `modules/`
- `data/`
- `tests/`
- old Core files not in the new structure: `amadeus_core/app.py`, `amadeus_core/core_controller.py`, `amadeus_core/core_services.py`, `amadeus_core/global_config.py`, `amadeus_core/logger.py`, `amadeus_core/module_loader.py`, `amadeus_core/permission_guard.py`, `amadeus_core/router.py`
- old docs: `docs/CORE_OVERVIEW.md`, `docs/ARCHITECTURE_LAWS.md`

Keep these planning artifacts unless the user explicitly asks to remove them:

- `docs/superpowers/specs/2026-06-30-amadeus-modular-shell-design.md`
- `docs/superpowers/plans/2026-06-30-amadeus-modular-shell.md`

---

### Task 1: Reset Root Project Shell

**Files:**
- Create/Replace: `D:\MAIN_AMADEUS\README.md`
- Create/Replace: `D:\MAIN_AMADEUS\requirements.txt`
- Create/Replace: `D:\MAIN_AMADEUS\.gitignore`
- Remove: obsolete files listed in the File Structure section

**Interfaces:**
- Consumes: approved design spec at `docs/superpowers/specs/2026-06-30-amadeus-modular-shell-design.md`
- Produces: clean root project metadata for later tasks

- [ ] **Step 1: Remove previous Core-only runtime and obsolete files**

Remove only the obsolete files listed in this plan. Do not remove `.git/` or `docs/superpowers/`.

- [ ] **Step 2: Write root README**

Replace `README.md` with:

```markdown
# AMADEUS

AMADEUS is a local-first personal AI project designed to grow as a clean modular desktop system.

This first rebuild is intentionally small. It creates a working shell with:

- AMADEUS Core
- AMADEUS Chat module
- AMADEUS PyQt6 GUI
- Placeholder folders for future modules

## Current Behavior

The app opens a desktop window. You can type a message, press Send or Enter, and AMADEUS returns a placeholder response:

```text
AMADEUS received: your message
```

## How To Run

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

This version does not include real reasoning, memory, skills, mind map, storage, permissions, or LLM connections yet.
```

- [ ] **Step 3: Write requirements**

Replace `requirements.txt` with:

```text
PyQt6>=6.7
```

- [ ] **Step 4: Write gitignore**

Replace `.gitignore` with:

```gitignore
__pycache__/
*.py[cod]
*$py.class

.venv/
venv/
env/

.idea/
.vscode/
*.swp
*.swo

*.log
*.tmp
*.temp
.DS_Store
Thumbs.db
```

- [ ] **Step 5: Verify root files exist**

Run:

```powershell
Test-Path -LiteralPath "D:\MAIN_AMADEUS\README.md"; Test-Path -LiteralPath "D:\MAIN_AMADEUS\requirements.txt"; Test-Path -LiteralPath "D:\MAIN_AMADEUS\.gitignore"
```

Expected:

```text
True
True
True
```

- [ ] **Step 6: Commit checkpoint**

Only run this if commits are explicitly approved for the session:

```bash
git add README.md requirements.txt .gitignore
git commit -m "chore: reset amadeus project shell"
```

---

### Task 2: Implement Core Registry And Chat Module

**Files:**
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_core\__init__.py`
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_core\module_registry.py`
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_core\core.py`
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_chat\__init__.py`
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_chat\chat_module.py`

**Interfaces:**
- Consumes: no prior runtime code
- Produces: `AmadeusCore.handle_user_message(message: str) -> str`, `ModuleRegistry.register(name: str, module: object) -> None`, `ModuleRegistry.get(name: str) -> object | None`, `AmadeusChatModule.handle_message(message: str) -> str`

- [ ] **Step 1: Write `amadeus_core/__init__.py`**

```python
"""AMADEUS Core package."""

from amadeus_core.core import AmadeusCore

__all__ = ["AmadeusCore"]
```

- [ ] **Step 2: Write `amadeus_core/module_registry.py`**

```python
class ModuleRegistry:
    """Stores module objects by name so Core can route without owning module logic."""

    def __init__(self) -> None:
        # The registry stores module entry objects only. It does not execute module behavior.
        self._modules: dict[str, object] = {}

    def register(self, name: str, module: object) -> None:
        """Register a module object under a stable module name."""
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("Module name cannot be empty.")

        self._modules[clean_name] = module

    def get(self, name: str) -> object | None:
        """Return a registered module object, or None if it is missing."""
        return self._modules.get(name.strip().lower())

    def list_modules(self) -> list[str]:
        """Return registered module names in predictable order."""
        return sorted(self._modules)
```

- [ ] **Step 3: Write `amadeus_chat/__init__.py`**

```python
"""AMADEUS Chat module package."""

from amadeus_chat.chat_module import AmadeusChatModule

__all__ = ["AmadeusChatModule"]
```

- [ ] **Step 4: Write `amadeus_chat/chat_module.py`**

```python
class AmadeusChatModule:
    """First simple chat module for the AMADEUS shell."""

    def handle_message(self, message: str) -> str:
        """Return a placeholder AMADEUS response for the provided user message."""
        clean_message = message.strip()

        # Later this boundary will connect to reasoning and the LLM client.
        # For now, the chat module only proves that Core can route to a module.
        return f"AMADEUS received: {clean_message}"
```

- [ ] **Step 5: Write `amadeus_core/core.py`**

```python
from amadeus_chat import AmadeusChatModule
from amadeus_core.module_registry import ModuleRegistry


class AmadeusCore:
    """Lightweight coordinator for AMADEUS modules."""

    def __init__(self) -> None:
        # Core owns coordination and routing. Modules own their own behavior.
        self.module_registry = ModuleRegistry()
        self._register_builtin_modules()

    def _register_builtin_modules(self) -> None:
        """Register the first built-in modules needed by the shell."""
        self.module_registry.register("chat", AmadeusChatModule())

    def handle_user_message(self, message: str) -> str:
        """Route user text to the chat module and return the module response."""
        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            return "AMADEUS error: chat module is not registered."

        # Core routes the message but does not generate the chat response itself.
        return chat_module.handle_message(message)  # type: ignore[attr-defined]
```

- [ ] **Step 6: Verify Core routes to Chat**

Run:

```powershell
py -3 -c "from amadeus_core.core import AmadeusCore; core = AmadeusCore(); print(core.handle_user_message('hello'))"
```

Expected:

```text
AMADEUS received: hello
```

- [ ] **Step 7: Commit checkpoint**

Only run this if commits are explicitly approved for the session:

```bash
git add amadeus_core amadeus_chat
git commit -m "feat: add core routing and chat module"
```

---

### Task 3: Implement PyQt6 GUI And Entry Point

**Files:**
- Create/Replace: `D:\MAIN_AMADEUS\main.py`
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_gui\__init__.py`
- Create/Replace: `D:\MAIN_AMADEUS\amadeus_gui\main_window.py`

**Interfaces:**
- Consumes: `AmadeusCore.handle_user_message(message: str) -> str`
- Produces: `AmadeusMainWindow(core: AmadeusCore)` and runnable `main.py`

- [ ] **Step 1: Install PyQt6 if missing**

Run:

```powershell
py -3 -m pip install -r requirements.txt
```

Expected: pip reports PyQt6 installed or already satisfied.

- [ ] **Step 2: Write `amadeus_gui/__init__.py`**

```python
"""AMADEUS GUI package."""

from amadeus_gui.main_window import AmadeusMainWindow

__all__ = ["AmadeusMainWindow"]
```

- [ ] **Step 3: Write `amadeus_gui/main_window.py`**

```python
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from amadeus_core import AmadeusCore


class AmadeusMainWindow(QMainWindow):
    """Main desktop window for the first AMADEUS feedback loop."""

    def __init__(self, core: AmadeusCore) -> None:
        super().__init__()
        self.core = core

        self.setWindowTitle("AMADEUS")
        self.resize(800, 600)

        self._build_ui()

    def _build_ui(self) -> None:
        """Create the chat history, input box, and send button."""
        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("AMADEUS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 8px;")

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Conversation will appear here.")

        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message to AMADEUS...")
        self.message_input.returnPressed.connect(self.send_message)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_message)

        input_row.addWidget(self.message_input)
        input_row.addWidget(send_button)

        layout.addWidget(title)
        layout.addWidget(self.chat_history)
        layout.addLayout(input_row)

        self.setCentralWidget(root)

    def send_message(self) -> None:
        """Send user text through Core and display the response."""
        message = self.message_input.text().strip()
        if not message:
            return

        self.message_input.clear()
        self._append_message("User", message)

        # GUI talks to Core only. Core decides which module handles the message.
        response = self.core.handle_user_message(message)
        self._append_message("AMADEUS", response)

    def _append_message(self, speaker: str, message: str) -> None:
        """Append one speaker line to the chat history."""
        self.chat_history.append(f"{speaker}: {message}")
```

- [ ] **Step 4: Write `main.py`**

```python
import sys

from PyQt6.QtWidgets import QApplication

from amadeus_core import AmadeusCore
from amadeus_gui import AmadeusMainWindow


def main() -> int:
    """Start AMADEUS Core, create the GUI, and run the desktop event loop."""
    app = QApplication(sys.argv)

    # Core is created before the GUI so the GUI can route all user actions through it.
    core = AmadeusCore()
    window = AmadeusMainWindow(core)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Verify GUI modules import**

Run:

```powershell
py -3 -c "from amadeus_core import AmadeusCore; from amadeus_gui import AmadeusMainWindow; print('gui import ok')"
```

Expected:

```text
gui import ok
```

- [ ] **Step 6: Manually verify the window**

Run:

```powershell
py -3 main.py
```

Expected:

- A window titled `AMADEUS` opens.
- Typing `hello` and pressing Send displays `User: hello`.
- The next line displays `AMADEUS: AMADEUS received: hello`.
- Pressing Enter in the input field also sends the message.

- [ ] **Step 7: Commit checkpoint**

Only run this if commits are explicitly approved for the session:

```bash
git add main.py amadeus_gui
git commit -m "feat: add pyqt amadeus gui"
```

---

### Task 4: Add Module Documentation And Placeholder Packages

**Files:**
- Create/Replace: module docs in `amadeus_core`, `amadeus_chat`, `amadeus_gui`, `reasoning_module`, `skills`, `mindmap`, `storage`, `llm_client`, `permissions`
- Create/Replace: `reasoning_module/__init__.py`
- Create/Replace: `skills/__init__.py`
- Create/Replace: `mindmap/__init__.py`
- Create/Replace: `storage/__init__.py`
- Create/Replace: `llm_client/__init__.py`
- Create/Replace: `permissions/__init__.py`

**Interfaces:**
- Consumes: folder boundaries from the approved architecture
- Produces: documented module folders ready for future expansion

- [ ] **Step 1: Write placeholder `__init__.py` files**

Use this exact content for each placeholder package `__init__.py`:

```python
"""Placeholder package for a future AMADEUS module."""
```

Files:

- `reasoning_module/__init__.py`
- `skills/__init__.py`
- `mindmap/__init__.py`
- `storage/__init__.py`
- `llm_client/__init__.py`
- `permissions/__init__.py`

- [ ] **Step 2: Write `amadeus_core` docs**

`amadeus_core/README.md`:

```markdown
# AMADEUS Core

Core is the lightweight coordinator for AMADEUS.

It registers modules and routes user requests to the correct module. Core should stay small and should not contain feature logic that belongs inside modules.
```

`amadeus_core/FEATURES.md`:

```markdown
# AMADEUS Core Features

- Creates a module registry.
- Registers the Chat module.
- Routes user messages to Chat.
```

`amadeus_core/FUTURE_UPDATES.md`:

```markdown
# AMADEUS Core Future Updates

- Formal module interface contract.
- Module health/status reporting.
- Command routing beyond chat.
- Permission-aware routing for risky actions.
```

- [ ] **Step 3: Write `amadeus_chat` docs**

`amadeus_chat/README.md`:

```markdown
# AMADEUS Chat

The Chat module handles conversational messages.

In this first version it returns a placeholder response so the AMADEUS feedback loop works before real AI logic is added.
```

`amadeus_chat/FEATURES.md`:

```markdown
# AMADEUS Chat Features

- Receives a text message from Core.
- Returns `AMADEUS received: <message>`.
```

`amadeus_chat/FUTURE_UPDATES.md`:

```markdown
# AMADEUS Chat Future Updates

- Connect to the Reasoning module.
- Connect to the LLM client.
- Support conversation context.
- Support richer response formatting.
```

- [ ] **Step 4: Write `amadeus_gui` docs**

`amadeus_gui/README.md`:

```markdown
# AMADEUS GUI

The GUI module owns the desktop window and user interaction.

It displays chat history, accepts user input, and calls Core. It should not call feature modules directly.
```

`amadeus_gui/FEATURES.md`:

```markdown
# AMADEUS GUI Features

- PyQt6 main window titled `AMADEUS`.
- Chat history area.
- Message input box.
- Send button.
- Enter-to-send behavior.
```

`amadeus_gui/FUTURE_UPDATES.md`:

```markdown
# AMADEUS GUI Future Updates

- Module sidebar.
- Settings screen.
- Mind map view.
- Theme support.
- Status indicators for Core and modules.
```

- [ ] **Step 5: Write future module docs**

Use these exact docs:

`reasoning_module/README.md`:

```markdown
# Reasoning Module

Future module for planning, reflection, and structured thinking before AMADEUS answers.
```

`reasoning_module/FEATURES.md`:

```markdown
# Reasoning Module Features

- No implemented features yet.
```

`reasoning_module/FUTURE_UPDATES.md`:

```markdown
# Reasoning Module Future Updates

- Think before answers.
- Break down complex requests.
- Choose which modules should act.
```

`skills/README.md`:

```markdown
# Skills

Future module for AMADEUS abilities and task-specific tools.
```

`skills/FEATURES.md`:

```markdown
# Skills Features

- No implemented features yet.
```

`skills/FUTURE_UPDATES.md`:

```markdown
# Skills Future Updates

- Register abilities.
- Execute safe actions through Core.
- Describe skill requirements and permissions.
```

`mindmap/README.md`:

```markdown
# Mind Map

Future module for visual concept mapping and idea organization.
```

`mindmap/FEATURES.md`:

```markdown
# Mind Map Features

- No implemented features yet.
```

`mindmap/FUTURE_UPDATES.md`:

```markdown
# Mind Map Future Updates

- Create nodes and links.
- Show concepts visually in the GUI.
- Connect ideas to memory and chat context.
```

`storage/README.md`:

```markdown
# Storage

Future module for persisted AMADEUS memory and project data.
```

`storage/FEATURES.md`:

```markdown
# Storage Features

- No implemented features yet.
```

`storage/FUTURE_UPDATES.md`:

```markdown
# Storage Future Updates

- Store conversations.
- Store memory.
- Store module data safely.
```

`llm_client/README.md`:

```markdown
# LLM Client

Future module for connecting AMADEUS to local or cloud language models.
```

`llm_client/FEATURES.md`:

```markdown
# LLM Client Features

- No implemented features yet.
```

`llm_client/FUTURE_UPDATES.md`:

```markdown
# LLM Client Future Updates

- Connect to local models.
- Connect to cloud model APIs.
- Provide one stable model interface to other modules.
```

`permissions/README.md`:

```markdown
# Permissions

Future module for protecting risky AMADEUS actions.
```

`permissions/FEATURES.md`:

```markdown
# Permissions Features

- No implemented features yet.
```

`permissions/FUTURE_UPDATES.md`:

```markdown
# Permissions Future Updates

- Classify risky actions.
- Require approval for system changes.
- Record permission decisions clearly.
```

- [ ] **Step 6: Verify every module folder has required docs**

Run:

```powershell
py -3 -c "from pathlib import Path; folders=['amadeus_core','amadeus_chat','amadeus_gui','reasoning_module','skills','mindmap','storage','llm_client','permissions']; missing=[]; required=['README.md','FEATURES.md','FUTURE_UPDATES.md']; [missing.append(str(Path(folder)/name)) for folder in folders for name in required if not (Path(folder)/name).exists()]; print('missing:', missing)"
```

Expected:

```text
missing: []
```

- [ ] **Step 7: Commit checkpoint**

Only run this if commits are explicitly approved for the session:

```bash
git add amadeus_core amadeus_chat amadeus_gui reasoning_module skills mindmap storage llm_client permissions
git commit -m "docs: add module documentation"
```

---

### Task 5: Add Project Architecture Docs And Final Verification

**Files:**
- Create/Replace: `D:\MAIN_AMADEUS\docs\ARCHITECTURE.md`
- Create/Replace: `D:\MAIN_AMADEUS\docs\MODULE_RULES.md`
- Create/Replace: `D:\MAIN_AMADEUS\docs\FIRST_STEPS.md`

**Interfaces:**
- Consumes: implemented shell structure and approved design
- Produces: documented architecture and verified runnable app

- [ ] **Step 1: Write `docs/ARCHITECTURE.md`**

```markdown
# AMADEUS Architecture

AMADEUS is designed as a modular local-first personal AI system.

## Core Routes

Core coordinates the system. It registers modules and routes requests to them.

## Modules Execute

Modules own their behavior. Core should not contain chat logic, reasoning logic, memory logic, or UI internals.

## Submodules Extend Modules

Submodules will be internal pieces owned by a module. Core should not reach into submodules directly.

## Skills Provide Abilities

Skills will provide specific actions AMADEUS can perform later.

## Reasoning Thinks Before Answers

The Reasoning module will eventually decide how AMADEUS should think through a request before answering.

## Storage Persists Memory And Data

The Storage module will eventually persist conversations, memory, and module data.

## Permissions Protect Risky Actions

The Permissions module will eventually protect file edits, commands, system changes, and other risky actions.

## LLM Client Connects Models

The LLM Client module will eventually connect AMADEUS to local or cloud models through one stable interface.
```

- [ ] **Step 2: Write `docs/MODULE_RULES.md`**

```markdown
# AMADEUS Module Rules

1. Every major system gets its own folder.
2. Every module folder must include `README.md`, `FEATURES.md`, and `FUTURE_UPDATES.md`.
3. Modules should not directly control unrelated modules.
4. Core coordinates communication between modules.
5. GUI calls Core, not feature modules directly.
6. Core routes, modules execute.
7. Placeholder modules should stay simple until their real purpose is implemented.
```

- [ ] **Step 3: Write `docs/FIRST_STEPS.md`**

```markdown
# AMADEUS First Steps

This first version creates a working AMADEUS shell.

## Created Now

- Core module registry.
- Core message routing.
- Placeholder Chat module.
- PyQt6 GUI window.
- Placeholder folders for future modules.
- Documentation for every module folder.

## What Works Now

You can open the AMADEUS window, type a message, press Send or Enter, and see a placeholder AMADEUS response.

## What Should Come Next

The next step should be a formal module interface contract so future modules can register capabilities, expose commands, report status, and request permission-protected actions.
```

- [ ] **Step 4: Compile Python files**

Run:

```powershell
py -3 -m compileall .
```

Expected: no syntax errors.

- [ ] **Step 5: Verify Core response**

Run:

```powershell
py -3 -c "from amadeus_core import AmadeusCore; print(AmadeusCore().handle_user_message('test message'))"
```

Expected:

```text
AMADEUS received: test message
```

- [ ] **Step 6: Launch final app**

Run:

```powershell
py -3 main.py
```

Expected:

- A GUI window titled `AMADEUS` opens.
- Send button works.
- Enter key works.
- User line appears as `User: my message`.
- AMADEUS line appears as `AMADEUS: AMADEUS received: my message`.

- [ ] **Step 7: Check git diff**

Run:

```powershell
git status --short
git diff -- .
```

Expected: only intentional rebuild files changed.

- [ ] **Step 8: Commit checkpoint**

Only run this if commits are explicitly approved for the session:

```bash
git add docs main.py README.md requirements.txt .gitignore amadeus_core amadeus_chat amadeus_gui reasoning_module skills mindmap storage llm_client permissions
git commit -m "feat: build amadeus modular shell"
```

---

## Self-Review

Spec coverage:

- Core shell: Task 2.
- PyQt6 GUI: Task 3.
- Chat module: Task 2.
- Placeholder future module folders: Task 4.
- Documentation for every module folder: Task 4.
- Root docs: Task 5.
- Run instructions and dependency requirement: Task 1.
- Acceptance behavior: Tasks 3 and 5.

Placeholder scan:

- The only use of the word placeholder refers to intentional placeholder app behavior required by the spec.
- No task contains unspecified implementation details.

Type consistency:

- `AmadeusCore.handle_user_message(message: str) -> str` is used consistently by GUI and verification commands.
- `AmadeusChatModule.handle_message(message: str) -> str` is used only by Core.
- `ModuleRegistry.register`, `ModuleRegistry.get`, and `ModuleRegistry.list_modules` are used consistently.
