# Flow Chat GUI Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Launch AMADEUS into a persistent Flow Chat home view with navigation to the existing dedicated chats and future module placeholders.

**Architecture:** A stacked PyQt shell retains each module view. Core routes Flow requests to a separate Flow persistence/context service that reuses the existing chat module, identity builder, LLM client, and shared process event logger. A registry exposes only dedicated-chat metadata through the existing chat store.

**Tech Stack:** Python 3, PyQt6, unittest, JSON/JSONL local storage, Ollama client.

## Global Constraints

- Preserve the Core-routes/modules-execute/submodules-extend architecture.
- Do not read storage directly from GUI views.
- Do not inject dedicated-chat message bodies into Flow context.
- Keep runtime data untracked and preserve unrelated untracked files.
- Reuse `TraceLogger` and the shared process-event emitter.

---

### Task 1: Flow persistence and Chat Registry

**Files:**
- Create: `flow_chat/flow_chat_store.py`
- Create: `chat_registry/chat_registry.py`
- Modify: `storage/__init__.py`
- Test: `tests/test_flow_chat.py`

**Interfaces:**
- Produces `FlowChatStore.load_messages()`, `FlowChatStore.append_message(speaker, message)`, and `ChatRegistry.list_chat_metadata()`.
- `ChatRegistry` consumes `ChatHistoryStore.list_chats()` only.

- [x] Write persistence and registry tests for ordering, malformed storage, metadata-only output, and mutations.
- [x] Implement JSONL Flow message storage and a frozen `ChatMetadata` registry projection.
- [x] Run `py -3 -m unittest tests.test_flow_chat -v`.

### Task 2: Flow context and Core route

**Files:**
- Create: `flow_chat/flow_context_builder.py`
- Create: `flow_chat/flow_chat_service.py`
- Modify: `amadeus_core/core.py`
- Test: `tests/test_flow_chat.py`

**Interfaces:**
- Produces `FlowContextBuilder.build_for_message(message, trace_logger)` and `AmadeusCore.handle_flow_message(message, event_listener)`.
- Reuses `AmadeusChatModule.handle_message()` and `TraceLogger`.

- [x] Write failing tests for separate Flow history/metadata context, no dedicated message body leakage, and successful/failed event runs.
- [x] Implement Flow context/service and Core composition/route.
- [x] Run focused Flow tests.

### Task 3: GUI shell and reusable views

**Files:**
- Create: `amadeus_gui/flow_chat_view.py`
- Create: `amadeus_gui/module_placeholder_view.py`
- Modify: `amadeus_gui/main/main_window.py`
- Test: `tests/test_flow_chat_gui.py`

**Interfaces:**
- `AmadeusMainWindow` exposes the five persistent views and selects Flow at startup.
- `FlowChatView` consumes only `AmadeusCore.handle_flow_message()` through a background worker.

- [x] Add shell tests for navigation, default Flow selection, retained view state, and placeholder creation.
- [x] Wrap existing dedicated-chat surface as the Chats stack page without changing its behavior.
- [x] Add sidebar navigation, Flow view, and named placeholders.
- [x] Run GUI and existing GUI regression tests.

### Task 4: Documentation, validation, and delivery

**Files:**
- Modify: `README.md`, `AMADEUS_CHANGELOG.md`
- Modify: `amadeus_gui/{README.md,FEATURES.md,FUTURE_UPDATES.md}`
- Modify: `amadeus_chat/{README.md,FEATURES.md,FUTURE_UPDATES.md}`
- Modify: `amadeus_core/{README.md,FEATURES.md,FUTURE_UPDATES.md}`
- Modify: `flow_chat/{README.md,FEATURES.md,FUTURE_UPDATES.md}`

- [x] Document Flow versus dedicated chats, context layers, registry limits, events, placeholders, and known limitations.
- [x] Run `py -3 -m compileall .` and `py -3 -m unittest discover -s tests -v`.
- [x] Review source/docs diff, stage intended paths, commit, and push.
