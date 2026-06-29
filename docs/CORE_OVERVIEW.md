# AMADEUS V2 Core Overview

AMADEUS Core is the lightweight coordinator for the AMADEUS V2 system. It starts the app, loads global configuration, sets up logging, creates safety and registry services, scans the `modules/` folder, and prepares a clean route for future modules to connect.

Core does not contain actual feature logic. Chat, Mind Map, Skills, Reasoning, Storage, RAG, Web, Coding, Drift, UI, and other feature systems will be modules or submodules later.

## What Core Controls

- Application startup order.
- Global paths and startup settings.
- Core logging.
- Basic permission checks.
- Module discovery through `module_manifest.json`.
- Module metadata registration.
- Safe shared `CoreServices` passed to modules later.
- Basic Core-only command routing.

## What Core Must Not Control

- Chat behavior.
- LLM calls.
- Memory or database storage.
- RAG pipelines.
- Web browsing.
- Coding tools.
- Mind map logic.
- Reasoning systems.
- UI rendering.
- Module internals or submodule internals.

## Future Module Connection Path

Modules will connect through a standard public boundary:

- `module_manifest.json` describes the module.
- `public_api.py` exposes the module public API.
- A module entry object provides the controlled interface Core can use.

Core must discover and register modules before it can route commands to them. Even later, Core should talk only to the module public API, never random files inside a module.
