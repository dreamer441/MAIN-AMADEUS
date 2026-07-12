# Annotation Module

The Annotation Module parses structured bracket commands at the start of a user message.

Annotations are not normal chat text. They tell AMADEUS how to interpret the message before it reaches normal chat.

The first supported annotation is `[file]`.

## Guided Annotation Builder

The GUI can now ask this module for suggestions while Dato types. The first flow is `/` → `[file]` → module → folder/file. This keeps exact commands structured instead of forcing the normal LLM to guess paths from natural language.

Exact file access is intentionally annotation-only. Normal chat can talk about project summaries, but `[file]` is the verified path for opening actual files.

## Memory Annotation

`[memory]` now follows the same guided annotation philosophy as `[file]`. It supports global memory, chat memory, and memory listing through the right-side panel.
