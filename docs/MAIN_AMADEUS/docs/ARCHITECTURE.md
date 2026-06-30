# AMADEUS Architecture

AMADEUS is designed as a modular local-first personal AI system.

## Core Routes

Core coordinates the system. It registers modules and routes requests to them.

## Modules Execute

Modules own their behavior. Core should not contain chat logic, reasoning logic, memory logic, or UI internals.

## Identity Defines AMADEUS

The Identity Module stores AMADEUS's global charter and builds the identity prompt used by Chat. Identity is global; reasoning profiles are temporary. Future coding, study, debugging, or research modes may change AMADEUS's method, but they should not erase her core identity.

## Submodules Extend Modules

Submodules will be internal pieces owned by a module. Core should not reach into submodules directly.

## Skills Provide Abilities

Skills will provide specific actions AMADEUS can perform later.

## Reasoning Thinks Before Answers

The Reasoning module will eventually decide how AMADEUS should think through a request before answering.

## Storage Persists Memory And Data

The Storage module currently persists the active chat as local JSONL runtime data under `data/chats/`. This is not long-term memory yet; it only lets the GUI resume recent conversation messages.

## Permissions Protect Risky Actions

The Permissions module will eventually protect file edits, commands, system changes, and other risky actions.

## LLM Client Connects Models

The LLM Client module currently connects AMADEUS to local Ollama models through one stable interface. Future model providers should connect through this module instead of being called directly by GUI or Core.

## Annotations Guide Structured Requests

Annotations are bracket commands such as `[file]`. Core checks annotations before normal chat and routes them to the Annotation module. Annotation handlers execute structured behavior without requiring the Chat module to understand file reading.

## Project File Reader Stays Read-Only

The Project File Reader reads module documentation and top-level Python file names only. It must not edit, delete, or deeply scan the project automatically.

Core may provide this read-only project context to Chat when the user asks about modules, files, README files, or project structure. Chat still does not read files directly.

Core also injects Identity Module context into normal Chat requests so AMADEUS has a stable global self-definition without hardcoding the full charter inside Chat.
