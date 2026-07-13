# Annotation Module - Current Features

## Purpose
The Annotation Module detects bracket-style commands such as `[file]` and routes them to deterministic handlers before normal chat.

## Implemented features

- Parses annotations from the beginning of a user message.
- Supports annotation names and arguments such as `[file][identity_module][files]`.
- Registers annotation handlers through an annotation registry.
- Provides annotation context objects so handlers can use approved modules without depending directly on Core.
- Supports `[identity]` inspection commands for AMADEUS identity prompts and charter text.
- Supports `[file]` read-only project inspection:
  - list available readable modules
  - read module docs
  - list exact direct files in a module
  - read exact safe text file content
  - read one exact line from a safe text file
  - count exact lines in a safe text file
- File annotations use Project File Reader and must not ask the LLM to guess file names or file contents.

## Examples

```text
[file]
[file][identity_module]
[file][identity_module][files]
[file][identity_module] read README.md
[file][identity_module] first line identity_charter.py
[file][identity_module] how many lines identity_charter.py
[identity]
[identity][prompt]
[identity][project]
[identity][charter]
```

## Annotation Suggestion Builder v1

- Typing `/` in the GUI can now show available implemented annotations.
- `[file]` has a guided selection path: annotation → module → folder/file.
- Annotation arguments preserve raw text so file names such as `core.py` no longer become `core_py`.
- Annotation handlers may return a normal chat response plus an optional side-panel payload.
- `[file][module][file.py]` now opens exact file content through the right-side Code Viewer instead of dumping code into chat.

## Current Exact File Access Rule

- Exact verified file access belongs to `[file]`.
- Normal user prompts may ask for project summaries/explanations, but they should not trigger exact file reads.
- This separation protects AMADEUS from guessing file content from natural language.

## Memory Annotation

- Added `[memory]` to slash suggestions.
- Added `[memory][global] text` for cross-chat memory.
- Added `[memory][chat] text` for current-chat memory.
- Added `[memory][list]`, `[memory][list][global]`, and `[memory][list][chat]` to open memory in the right panel.
- Annotation suggestions now guide `[memory] -> [global]/[chat]/[list]`.

## Sheets Annotation Added

- Added `[sheet]` as a structured annotation command.
- `[sheet]`, `[sheet][list]`, `[sheet][chat]`, and `[sheet][global]` open sheet lists in the right panel.
- `[sheet][chat][Sheet Title]` and `[sheet][global][Sheet Title]` open a selected sheet.
- `[sheet][scope][Sheet Title] prompt` injects one selected sheet as callable context for the current prompt.
- Slash suggestions now include `[sheet]` and visible sheet titles.

## Export Annotation

- Added `[export]` as a structured annotation.
- Export annotation supports list/current chat/title/range forms.
- Export range prompts become callable context, not always-active memory.
- Slash suggestions now include `[export]` and export title/range guidance.

## Export Annotation Accuracy Update

- `[export]` now supports clearer mode-first paths:
  - `[export][open][Chat Title][4-6]`
  - `[export][use][Chat Title][4-6] prompt`
- Legacy shorthand `[export][Chat Title][4-6] prompt` still works.
- Export suggestions now prefer `[open]` and `[use]` so Dato can see whether he is only opening Materials or injecting context into AMADEUS.
- Export prompt injection is scoped to the selected exported messages and should not fall back to current chat context.

## Phase 3 Annotation Engine V2

- Annotations can appear anywhere in a complete message as independent blocks.
- `[annotation][arguments] content [end]` closes one block; an omitted `[end]` consumes the rest of the message.
- Blocks do not nest: bracket text inside a block remains that block's content.
- The parser returns ordered blocks and only text outside completed blocks as the normal prompt.
- Existing single leading annotation syntax remains available unchanged.
- Slash suggestions include `[end]` for closing a block.
