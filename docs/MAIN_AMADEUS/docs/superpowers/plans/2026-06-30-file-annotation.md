# File Annotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only `[file]` annotations and switch default chat to installed `llama3.2:latest`.

**Architecture:** Core checks the annotation parser before normal chat. Parsed annotations route through `AnnotationRegistry` to `FileAnnotation`, which uses `ProjectFileReader`. GUI remains Core-only.

**Tech Stack:** Python 3, PyQt6, Ollama, standard library file/path tools.

## Global Constraints

- Work in `D:\MAIN_AMADEUS`.
- Do not recreate the project.
- Do not delete `qwen3:32b`.
- Default Ollama model becomes `llama3.2:latest`.
- File reading is read-only.
- Do not scan the whole project automatically.
- Do not add file editing, memory, reasoning, mind map, or advanced autonomy.

---

### Task 1: Model Switch

- Modify `llm_client/ollama_client.py` default model to `llama3.2:latest`.
- Update docs mentioning default model.
- Verify `OllamaClient().health_check()` reports model available.

### Task 2: Project File Reader

- Create `project_file_reader/` package.
- Implement `ProjectFileReader` and `ModuleIndexer`.
- Support module name normalization, safe module listing, doc reading, and top-level Python file listing.

### Task 3: Annotation Module

- Create `annotation_module/` package.
- Implement `ParsedAnnotation`, `AnnotationParser`, `AnnotationRegistry`, `AnnotationContext`, and `FileAnnotation`.
- Support `[file]`, `[file][amadeus_core]`, and `[file][amadeus core]`.

### Task 4: Core Integration

- Update `AmadeusCore` to create parser, registry, file reader, and file annotation.
- In `handle_user_message`, parse annotations first; route annotation if present; otherwise route normal chat.

### Task 5: Docs And Verification

- Add docs for every new module folder.
- Update architecture docs and README.
- Verify compile, parser behavior, file annotation behavior, normal chat, GUI offscreen path, git status.
- Commit and push.
