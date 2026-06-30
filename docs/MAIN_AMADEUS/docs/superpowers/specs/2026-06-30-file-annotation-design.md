# File Annotation Design

Date: 2026-06-30

## Goal

Extend the current AMADEUS shell with the first annotation command, `[file]`, and a read-only project file reader. Do not recreate the project or rewrite the shell.

## Active Project Path

The active repository is `D:\MAIN_AMADEUS`. The requested path `D:\MAIN AMADEUS` does not exist on disk.

## Model Change

Change the default Ollama model from `qwen3:32b` to installed `llama3.2:latest` for lighter day-to-day chat. Keep `qwen3:32b` installed for heavier tasks.

## Architecture

The new flow is:

```text
GUI -> Core -> Annotation Parser
              -> Annotation Registry -> FileAnnotation -> ProjectFileReader
              -> Chat Module -> LLM Client
```

Core remains the coordinator. GUI still calls only `core.handle_user_message()`. Chat does not call the file reader.

## Modules

### annotation_module

Responsibilities:

- Parse leading bracket annotations such as `[file]`, `[file][amadeus_core]`, and `[file][amadeus core]`.
- Normalize annotation and argument names.
- Register annotation handlers by name.
- Route parsed annotations to the correct handler.

### project_file_reader

Responsibilities:

- Read project files safely and read-only.
- List top-level module folders.
- Read `README.md`, `FEATURES.md`, and `FUTURE_UPDATES.md` for a requested module.
- List Python files in the requested module folder only.
- Ignore hidden/system folders such as `.git`, `__pycache__`, `.venv`, and `venv`.

## File Annotation Behavior

`[file]` returns available module options in the format:

```text
Available project modules:

* [file][amadeus_core]
* [file][amadeus_chat]
...
```

`[file][amadeus_core]` reads only:

1. `amadeus_core/README.md`
2. `amadeus_core/FEATURES.md`
3. `amadeus_core/FUTURE_UPDATES.md`

It then returns a structured summary with the module name, documentation sections, and important Python files in that folder only.

If the requested module is missing, return a clear error and closest module suggestions.

## Exclusions

- No file editing.
- No memory.
- No reasoning module.
- No mind map.
- No advanced autonomy.
- No full-project scan.
- No automatic deep code inspection.

## Verification

- Normal chat still routes to Chat and Ollama.
- `[file]` lists available modules.
- `[file][amadeus_core]` returns structured documentation and Python files for `amadeus_core` only.
- Unknown modules return suggestions without crashing.
- GUI import and offscreen send path still work.
