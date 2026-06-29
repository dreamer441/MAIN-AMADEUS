# AMADEUS V2 Core Foundation

This is the initial Core-only foundation for AMADEUS V2, a local-first modular AI system.

This version intentionally includes only the Core layer. It does not include Chat, Mind Map, Skills, Reasoning, Storage, RAG, Web, Coding, Drift, UI, or real modules yet.

## Current Scope

- Start AMADEUS Core.
- Load global config.
- Start console and file logging.
- Create `PermissionGuard`.
- Create `ModuleRegistry`.
- Create `ModuleLoader`.
- Scan the `modules/` folder.
- Report that no modules are installed yet.
- Create `CoreServices`.
- Exit normally.

## How To Run

```bash
python main.py
```

## Module Rule

Core must not import module internals. Future modules will connect through:

- `module_manifest.json`
- `public_api.py`
- a module entry object
