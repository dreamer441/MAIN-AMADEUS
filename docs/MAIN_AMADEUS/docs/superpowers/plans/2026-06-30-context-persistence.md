# Project Context And Chat Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add implicit read-only project context for normal file/module questions and persist the current chat locally.

**Architecture:** Core detects project/file intent, gathers context through `ProjectFileReader`, passes it to Chat, and persists exchanges through Storage. GUI loads history through Core.

**Tech Stack:** Python 3 standard library JSONL storage, existing PyQt6 GUI, existing Ollama chat module.

## Global Constraints

- Do not add file editing.
- Do not deep scan the whole project.
- Do not add long-term memory or a database.
- Keep GUI calling Core only.
- Keep Chat from reading files directly.
- Keep chat history out of git.

---

### Task 1: Storage

- Add `storage/chat_history_store.py`.
- Append messages as JSONL records.
- Load recent messages for GUI resume.

### Task 2: Project Context

- Add `ProjectFileReader.build_project_overview()`.
- Include documented module folders, module docs, and top-level Python file names.
- Pass context only when Core detects file/module/project wording.

### Task 3: Core And GUI Integration

- Persist user/AMADEUS exchanges from Core.
- Add `Core.load_chat_history()`.
- Load saved history in the GUI after UI construction.

### Task 4: Docs And Verification

- Ignore `data/chats/`.
- Update docs.
- Verify compile, fake context injection, live chat, `[file]`, and GUI history loading.
