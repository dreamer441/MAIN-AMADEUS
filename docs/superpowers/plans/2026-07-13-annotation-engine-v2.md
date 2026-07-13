# Annotation Engine V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support independently delimited annotation blocks anywhere in a message while preserving legacy leading annotation commands.

**Architecture:** `AnnotationParser` owns recognition and extraction of block syntax, returning ordered parsed blocks and text outside completed blocks. Core consumes this parsed result, executes deterministic blocks through existing annotation routes, and sends only outside text to normal chat with the block results as callable context. The GUI owns suggestion-list key behavior.

**Tech Stack:** Python 3, `unittest`, PyQt6.

## Global Constraints

- Preserve `AnnotationParser.parse()` behavior for existing leading syntax.
- Core must not parse `[end]` or scan block syntax.
- Blocks are non-nested, independent, and run in source order.
- Only text outside completed blocks is the normal-chat prompt.
- Do not commit or push this work.

---

### Task 1: Parser Block Extraction

**Files:**
- Modify: `annotation_module/annotation_parser.py`
- Create: `tests/test_annotation_parser.py`

**Interfaces:**
- Produces: `AnnotationBlock` and `ParsedAnnotationMessage` dataclasses plus `AnnotationParser.parse_message(message: str) -> ParsedAnnotationMessage`.

- [x] Add parser tests for annotations embedded in text, multiple `[end]`-delimited blocks, unterminated blocks consuming message end, no nested parsing, and legacy `parse()` compatibility.
- [x] Implement block extraction in `AnnotationParser`, reusing the legacy parser for each block and retaining only text outside completed blocks as `normal_prompt`.
- [x] Run focused parser tests through discovery.

### Task 2: Core Block Execution

**Files:**
- Modify: `amadeus_core/core.py`
- Create: `tests/test_annotation_core.py`

**Interfaces:**
- Consumes: `AnnotationParser.parse_message()`.
- Produces: one deterministic combined response for block-only input, or one normal-chat response with labelled deterministic callable context for outside text.

- [x] Add Core tests using a fake chat module and deterministic annotation registry handlers to verify ordered execution and outside-text-only chat input; parser tests cover legacy leading syntax.
- [x] Add a Core helper that consumes parser output, dispatches deterministic annotation blocks through the registry, and builds one normal-chat request only when `normal_prompt` is non-empty.
- [x] Keep callable sheet/export routing in `CallableContextRouter` for the existing legacy one-annotation path; block extraction syntax remains absent from Core.
- [x] Run focused Core tests through discovery.

### Task 3: Suggestions And GUI Keyboard Controls

**Files:**
- Modify: `annotation_module/annotation_suggestions.py`
- Modify: `amadeus_gui/main/main_window.py`
- Create: `tests/test_annotation_gui.py`

**Interfaces:**
- Produces: `/end` suggestion and visible-list Up/Down/Enter/Tab/Escape behavior without changing closed-input behavior.

- [x] Add `/end` to slash suggestions.
- [x] Inject suggestion popup callbacks into `MessageInput`; consume navigation/insertion/hide keys only while the list is visible.
- [x] Add offscreen PyQt tests for selection navigation, insertion, hiding, and ordinary Enter send behavior when no list is visible.
- [x] Run focused GUI tests through discovery.

### Task 4: Documentation And Validation

**Files:**
- Modify: `annotation_module/FEATURES.md`
- Modify: `annotation_module/FUTURE_UPDATES.md`
- Modify: `amadeus_core/FEATURES.md`
- Modify: `amadeus_core/FUTURE_UPDATES.md`
- Modify: `amadeus_gui/FEATURES.md`
- Modify: `amadeus_gui/FUTURE_UPDATES.md`
- Modify: `AMADEUS_CHANGELOG.md`

- [x] Describe supported block grammar, result composition, GUI keys, and remaining limitations in affected module documentation.
- [x] Append the required structured Phase 3 changelog entry.
- [x] Run `py -3 -m compileall .` and `py -3 -m unittest discover -s tests -v`.
- [x] Review `git status --short` and `git diff --stat`; do not stage, commit, or push files.
