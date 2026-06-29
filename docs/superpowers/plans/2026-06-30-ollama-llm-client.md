# Ollama LLM Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect AMADEUS Chat to a local Ollama model through the `llm_client` module.

**Architecture:** GUI continues to call Core only. Core creates the LLM client and passes it to Chat. Chat owns conversational behavior and asks `llm_client` for model output.

**Tech Stack:** Python 3, PyQt6, Ollama local HTTP API, Python standard library `urllib` and `json` for HTTP calls.

## Global Constraints

- Work in `D:\MAIN_AMADEUS`.
- Default Ollama model is `qwen3:32b`.
- Preserve `GUI -> Core -> Chat Module -> LLM Client -> Ollama`.
- Core routes; modules execute.
- GUI calls Core, not Chat directly.
- Do not build streaming responses.
- Do not build memory.
- Do not build reasoning integration.
- Do not build model picker UI.
- Do not add cloud model providers.
- Commit and push the final intended project state to `origin/main`.

---

### Task 1: Add Ollama Client

**Files:**
- Create: `D:\MAIN_AMADEUS\llm_client\ollama_client.py`
- Modify: `D:\MAIN_AMADEUS\llm_client\__init__.py`

**Interfaces:**
- Produces: `DEFAULT_OLLAMA_MODEL: str`, `OllamaClientError`, `OllamaClient.generate(prompt: str, system_prompt: str | None = None) -> str`, `OllamaClient.health_check() -> dict[str, object]`

- [ ] **Step 1: Create Ollama client implementation**

Implement `llm_client/ollama_client.py` with a standard-library HTTP client for `http://localhost:11434/api/generate` and `http://localhost:11434/api/tags`.

- [ ] **Step 2: Export the client**

Update `llm_client/__init__.py` to export `DEFAULT_OLLAMA_MODEL`, `OllamaClient`, and `OllamaClientError`.

- [ ] **Step 3: Verify import**

Run: `py -3 -c "from llm_client import DEFAULT_OLLAMA_MODEL, OllamaClient; print(DEFAULT_OLLAMA_MODEL); print(type(OllamaClient()).__name__)"`

Expected output includes `qwen3:32b` and `OllamaClient`.

---

### Task 2: Wire Chat Through LLM Client

**Files:**
- Modify: `D:\MAIN_AMADEUS\amadeus_chat\chat_module.py`
- Modify: `D:\MAIN_AMADEUS\amadeus_core\core.py`

**Interfaces:**
- Consumes: `OllamaClient.generate(prompt: str, system_prompt: str | None = None) -> str`
- Produces: `AmadeusChatModule(llm_client: object | None = None)`, `AmadeusChatModule.handle_message(message: str) -> str`, `AmadeusCore(llm_client: object | None = None)`

- [ ] **Step 1: Update Chat**

Make `AmadeusChatModule` accept an LLM client, build a simple prompt, call `generate`, and return clear error text when Ollama fails.

- [ ] **Step 2: Update Core**

Make `AmadeusCore` create `OllamaClient` and pass it into `AmadeusChatModule` while keeping Core as router only.

- [ ] **Step 3: Verify Core instantiation**

Run: `py -3 -c "from amadeus_core import AmadeusCore; core=AmadeusCore(); print(core.module_registry.list_modules())"`

Expected: `['chat']`.

---

### Task 3: Update Documentation

**Files:**
- Modify: `D:\MAIN_AMADEUS\README.md`
- Modify: `D:\MAIN_AMADEUS\amadeus_chat\README.md`
- Modify: `D:\MAIN_AMADEUS\amadeus_chat\FEATURES.md`
- Modify: `D:\MAIN_AMADEUS\amadeus_chat\FUTURE_UPDATES.md`
- Modify: `D:\MAIN_AMADEUS\llm_client\README.md`
- Modify: `D:\MAIN_AMADEUS\llm_client\FEATURES.md`
- Modify: `D:\MAIN_AMADEUS\llm_client\FUTURE_UPDATES.md`
- Modify: `D:\MAIN_AMADEUS\docs\ARCHITECTURE.md`
- Modify: `D:\MAIN_AMADEUS\docs\FIRST_STEPS.md`

**Interfaces:**
- Consumes: implemented Ollama client behavior.
- Produces: setup docs for `ollama pull qwen3:32b` and `py -3 main.py`.

- [ ] **Step 1: Update root docs**

Document that Ollama is now used for real local responses and that `qwen3:32b` must be pulled.

- [ ] **Step 2: Update module docs**

Document current Chat and LLM Client behavior without adding future features to code.

---

### Task 4: Verify, Commit, And Push

**Files:**
- All intended project changes.

**Interfaces:**
- Consumes: implemented Ollama client, Chat wiring, docs.
- Produces: pushed commit on `origin/main`.

- [ ] **Step 1: Check Ollama model state**

Run: `ollama list`.

- [ ] **Step 2: Pull model if missing**

Run if needed: `ollama pull qwen3:32b`.

- [ ] **Step 3: Compile Python files**

Run: `py -3 -m compileall main.py amadeus_core amadeus_chat amadeus_gui llm_client reasoning_module skills mindmap storage permissions`.

- [ ] **Step 4: Verify client health or clear setup error**

Run: `py -3 -c "from llm_client import OllamaClient; print(OllamaClient().health_check())"`.

- [ ] **Step 5: Verify GUI display path offscreen with fake Core**

Run an offscreen PyQt6 command that sends `my message` through `AmadeusMainWindow` using a fake core object and prints chat history.

- [ ] **Step 6: Inspect git state**

Run: `git status --short`, `git diff --stat`, and `git log --oneline -5`.

- [ ] **Step 7: Commit and push**

Run: `git add .`, `git commit -m "feat: build modular amadeus shell with ollama"`, and `git push -u origin main`.

---

## Self-Review

Spec coverage:

- Ollama client implementation: Task 1.
- Chat uses LLM client: Task 2.
- Core remains router: Task 2.
- GUI remains Core-only: no GUI architecture change; verified in Task 4.
- Docs updated: Task 3.
- Commit and push: Task 4.

Placeholder scan:

- No unspecified implementation steps remain.

Type consistency:

- `OllamaClient.generate(prompt: str, system_prompt: str | None = None) -> str` is consumed by Chat.
- `AmadeusCore(llm_client: object | None = None)` passes the dependency to Chat.
