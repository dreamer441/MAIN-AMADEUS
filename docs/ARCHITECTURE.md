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

The LLM Client module currently connects AMADEUS to local Ollama models through one stable interface. Future model providers should connect through this module instead of being called directly by GUI or Core.
