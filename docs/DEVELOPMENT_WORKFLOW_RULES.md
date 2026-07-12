# AMADEUS Development Workflow Rules

These rules exist because AMADEUS is becoming modular and complex. They are not optional style notes; they protect future development continuity and readability.

## 1. Module Documentation Must Stay Current

Every time a feature is added, changed, postponed, or discussed as a future step, update the related module documentation files:

- `README.md` explains the module purpose and boundaries.
- `FEATURES.md` records what is currently implemented.
- `FUTURE_UPDATES.md` records what should be built later.

If a change touches more than one module, update each affected module. If a future idea is discussed but not implemented yet, it belongs in `FUTURE_UPDATES.md`, not only in chat history.

## 2. Code Comments Are Part Of The Feature

AMADEUS code should be readable by Dato, not only executable by Python.

Comments should explain:

- why a module exists
- where data flows next
- which class owns which responsibility
- why a safety boundary exists
- how future modules should connect
- what must stay real execution data instead of fake hidden thinking

Avoid useless comments like `# add 1 to x`. Prefer comments that explain architecture and intent.

## 3. Small Stable Patches First

Do not rewrite the project when adding one feature. Extend the current structure carefully. Core should stay small, and feature-specific behavior should live in modules.

## 4. Documentation Before Moving On

Before starting the next feature, check whether the previous patch updated:

- affected module `FEATURES.md`
- affected module `FUTURE_UPDATES.md`
- relevant `README.md`
- comments in changed code files

If not, do a documentation/comment pass first.

## 5. Memory Changes Must Be Explicit

Long-term memory affects every future chat, so V1 memory must remain annotation-driven. AMADEUS should not silently save normal conversation as durable memory. If a future patch adds memory suggestions or automatic memory, it must include confirmation, trace logging, and documentation updates.
