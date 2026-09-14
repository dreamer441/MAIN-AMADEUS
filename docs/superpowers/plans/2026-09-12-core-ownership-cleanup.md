# Core Ownership Cleanup Implementation Plan

> **For agentic workers:** Use subagent-driven-development for bounded tasks and review, with the controller handling integration. Steps use checkbox syntax for tracking.

**Goal:** Make Core an explicit routing facade and move each workflow to its owner while preserving behavior.

**Architecture:** Application composition injects modules into the Core routing facade. Dedicated Chat, Flow, Canvas, Permissions and Workspace Integration own execution. Public compatibility imports forward to the new owners.

**Tech Stack:** Python, unittest, PyQt6, existing local JSON/JSONL/SQLite stores.

## Global Constraints

- Preserve all existing features and local data formats.
- Core routes. Modules execute. Submodules extend modules. Skills provide abilities. Storage stores. PermissionGuard protects.
- GUI operations route through Core and share application service instances.
- Never commit runtime data, caches, secrets, or temporary reports.
- Run `python -m compileall .` and relevant tests before committing and pushing.
- Do not reset or discard the pre-existing working tree.

## Task 1: Baseline and concrete ownership map

- [x] Capture source snapshot outside the repository; record initial Git state.
- [x] Write approved spec and implementation plan.
- [x] Locate Python/PyQt6 and record existing full-suite baseline.

## Task 2: Workspace and GUI boundaries

**Files:** `workspace_integration/*`, `mindmap/integrations/*`, `canvas_module/canvas_module.py`, `canvas_module/gui/view.py`, `habit_tracker/view.py`, `habit_tracker/core_adapter.py`, `amadeus_gui/main/main_window.py`, `sheets_module/sheet_service.py`, `annotation_module/annotations/sheet_annotation.py`, tests and affected docs.

**Interfaces:** Core exposes `canvas` and `habits` explicitly registered facades. Canvas facade forwards the existing CanvasModule public methods and read-only `workspace_id`; Habit facade forwards HabitTrackerService public methods. MainWindow passes `core.habits` into `HabitTrackerView(service=...)`. Core composition constructs one instance of each owner.

```python
# CanvasView binds the public Core facade, never Core's feature instance.
self.canvas_module = core.canvas
# MainWindow supplies the shared Core-routed Habit facade.
self.habit_tracker_view = HabitTrackerView(service=self.core.habits)
```

- [x] Move MindMapWorkspaceSync implementation into workspace_integration; retain compatibility re-export.
- [x] Replace private Canvas projection call with a validated public projection API.
- [x] Make GUI adapters call the explicit Core facades described above.
- [x] Remove Sheets -> Annotation import and resolve plain target values; preserve public compatibility if needed without importing parser types.
- [x] Add routing/dependency regression tests; update affected module docs.

## Task 3: Application composition and owner workflows

**Files:** `amadeus_app/*`, `amadeus_core/*`, `chat_workspace/*`, `flow_chat/request_handler.py`, `canvas_module/request_handler.py`, `permissions/*`, `habit_tracker/actions.py`, `inner_brain/*`, `response_modes/*`, affected tests/docs.

**Interfaces:** `compose_application(project_root, llm_client, inner_brain_service)` returns injected owner services. Core retains existing public methods as explicit one-line forwarding methods. Constructor arguments remain `llm_client=None, project_root=None, inner_brain_service=None`.

```python
def handle_user_message(self, message, callable_context=None,
                        event_listener=None, response_mode_override=None):
    return self.chat_workspace.handle_user_message(
        message, callable_context, event_listener, response_mode_override)
```

- [x] Extract composition from Core into amadeus_app.
- [x] Move pending-action records to permissions with compatibility re-export; dispatch owner actions through registered callbacks.
- [x] Move dedicated-chat execution, metadata and lifecycle into focused chat_workspace services; remove unused duplicate sheet/export execution paths.
- [x] Move Flow orchestration and Canvas response wrapping into their modules.
- [x] Move selected-context conversation execution out of Annotation into Chat Workspace while keeping syntax/context resolution with Annotation and owner services.
- [x] Keep Core explicit; no dynamic arbitrary getattr routing, giant replacement coordinator, or mixins containing feature behavior.
- [x] Keep existing public entry points; update tests that bypassed construction to test injected owner services instead.
- [x] Update docs including previously missing required module docs.

## Task 4: Regression, review and delivery

**Files:** `tests/test_architecture_boundaries.py`, `docs/CORE_CLEANUP_REPORT.md`, `docs/ARCHITECTURE.md`, `docs/MODULE_RULES.md`, `AMADEUS_CHANGELOG.md`, affected module docs, `.gitignore` if runtime coverage needs completion.

- [x] Verify Core contains no feature execution imports or storage calls.
- [x] Run focused tests after each extraction, then complete suite and compileall.
- [x] Independent spec and quality review of the cleanup diff against the source snapshot; resolve material findings.
- [x] Write change inventory and concrete manual test steps with expected results.
- [x] Review Git status and diff; stage only intended dependency-complete source/docs/tests/configuration. Inspect cached stat and exclude runtime/cache/secret paths.
- Delivery step: commit with `refactor: restore module ownership and slim core`; push current branch and record outcome.

Final validation: 336 full-suite tests and all 25 isolated modules passed; compileall passed. Independent architecture, integration and fixture reviews passed. Actual commit/push outcome is recorded in the task completion message.
