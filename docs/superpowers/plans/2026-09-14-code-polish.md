# Behavior Preserving Code Polish Implementation Plan

> **For agentic workers:** Use subagent-driven-development for independent owner-local extractions and review. Steps use checkbox syntax.

**Goal:** Make large UI implementations easier to maintain and remove local duplication without changing behavior.

**Architecture:** Keep GUI helpers inside their existing Canvas and Mind Map owners. Keep old view import names available as compatibility exports. Preserve Core routes and public service contracts.

**Tech Stack:** Python, PyQt6, unittest, existing module stores.

## Global Constraints

- No new features, dependency packages, storage migrations, prompt changes, approval changes or data changes.
- Core routes. Modules execute. Submodules extend modules. Skills provide abilities. Storage stores. PermissionGuard protects.
- Preserve public imports, widget behavior, class names, signal connections, defaults and ordering.
- Keep unrelated files and the supplied theory archive untouched.
- Validate existing behavior using focused tests, class-body equivalence checks where applicable, full unittest discovery and `python -m compileall .`.

## Task 1 Canvas presentation separation

Files: `canvas_module/gui/view.py`, new owner-local `dialogs.py`, `items.py`, `surface.py` as justified; Canvas README and module notes.

- [x] Move the existing editor/preview dialogs, graphics items and surface into focused files without changing method bodies. Shared constants belong beside their users or in one owner-local constants file. Preserve old imports through explicit imports in view.py.
- [x] Avoid circular imports: graphics items and dialogs receive their existing callbacks; helpers must never import CanvasView.
- [x] Compare moved class AST bodies against Git HEAD; run `test_canvas_module.py` and `test_workspace_boundaries.py` with offscreen Qt.

## Task 2 Mind Map presentation separation

Files: `mindmap/gui/view.py`, new `mindmap/gui/dialogs.py`, optional `surface.py`; Mind Map README and module notes.

- [x] Move node/link/import dialogs and canvas surface without changing behavior. Keep old class and constant imports available from view.py.
- [x] Consolidate identical unit interval spin-box setup within the dialog owner while preserving existing instance-method entry points.
- [x] Compare moved method bodies against Git HEAD apart from the explicit deduplication; run `test_mindmap.py` and `test_mindmap_annotation.py` with offscreen Qt.

## Task 3 Context ordering simplification and final validation

Files: `canvas_module/context.py`, this plan, `AMADEUS_CHANGELOG.md`, affected module documentation.

- [x] Replace the four repeated role-priority assignment loops with one ordered loop over role groups. Keep the same priority, distance fallback, coordinates, IDs and final ordering.

```python
for priority, object_ids, distances, fallback in (
    (0, target_object_ids, {}, 0),
    (1, ancestors, ancestor_distance, ancestor_depth + 1),
    (2, descendants, descendant_distance, descendant_depth + 1),
    (3, peers, peer_distance, peer_depth + 1),
):
    for object_id in object_ids:
        block = block_by_id[object_id]
        role_priority[object_id] = (
            priority, distances.get(object_id, fallback),
            block.position_y, block.position_x, object_id,
        )
```

- [x] Compare old/new context packages over generated representative snapshots and run existing Canvas tests; do not claim a speed improvement without measurement.
- [x] Review all source changes for unchanged contracts and GUI ownership; run the full 336-test suite and compileall.
- Delivery: record changes and test results in the changelog, stage only reviewed task paths, inspect cached stat, and make a local `refactor:` commit. The actual commit is recorded in the task completion message.
- Delivery: pushing remains blocked by the earlier automatic-review rejection until the user confirms the configured remote destination. Do not retry or bypass it without new authorization evidence.

## Validation record

- 336 full-suite tests passed in 81.759 seconds.
- 101 focused Canvas/Mind Map/boundary tests passed.
- 600 old/new Canvas context packages matched exactly.
- Python compileall passed.
- Original class ASTs are preserved except the documented spin-box helper delegation; compatibility imports and dialog defaults were checked.
- Independent final review passed: no unresolved GUI globals, import cycles, callback/default changes or blocking findings.
