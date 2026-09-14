# Core ownership cleanup report

Completed: 2026-09-14. Design approved and work started: 2026-09-12.

## Result

Core routes requests to explicit registered owners. Application setup, conversation
execution, approval dispatch and workspace synchronization now have separate homes.
The coordinator decreased from 1,787 to 650 lines; the remaining code consists of
explicit routes, service compatibility accessors and startup delegation.

The ownership rule remains: **Core routes; modules execute; submodules extend
modules; skills provide abilities; storage stores; PermissionGuard protects.**

## What changed

| Area | Final ownership and change |
|---|---|
| Application setup | New `amadeus_app/composition.py` creates and injects the application services once. |
| Core | `core_coordinator.py` explicitly forwards requests; `module_registry.require()` reports missing owners; `module_routes.py` supplies Canvas and Habit facades. Core can be imported and route-tested without Qt or feature imports. |
| Dedicated conversations | New `chat_workspace` groups conversation execution, selected-context conversations, chat lifecycle, metadata, workspace documents and exchange persistence. Generation still belongs to Chat; records belong to Storage. |
| Flow | `flow_chat/request_handler.py` owns Flow orchestration and isolated history routing. Existing deterministic Habit commands and approval behavior remain. |
| Canvas | `canvas_module/request_handler.py` owns request response wrapping. GUI operations use the Core Canvas facade. Public projection replacement validates inputs before changing the document. |
| Permissions | `permissions/guard.py` owns approved callback dispatch; pending records moved here. Scope freezes before approval, decline does not execute, and an approval is consumed before owner dispatch. |
| Creation | `requests.py` prepares creation requests; `approved_actions.py` dispatches approved creation through public owners; shared chat metadata generation moved from Flow into `chat_metadata.py`. |
| Habit Tracker | `actions.py` owns approved Habit operations. MainWindow injects the shared Core Habit facade into the view. Importing the service no longer eagerly loads Qt. |
| Workspace Integration | New owner package groups source synchronization, source-aware graph workflows and the creation adapter. Mind Map and Canvas still own their own stores. |
| Annotation | Keeps parsing, handlers and syntax interpretation. Suggestions and result unpacking have focused helpers. Selected-context conversation execution moved to Chat Workspace. |
| Context Builder | Owns bounded inferred read context and Mind Map context formatting. Inner Brain remains advisory. |
| Sheets | Accepts plain scope/reference values through `resolve_target`; no longer imports Annotation parser types. Annotation interprets annotation syntax. |
| Other owner workflows | Materials, Project File Reader and Side Ask each receive their own workspace/workflow helper; response payload presentation moves to Response Modes. |
| Compatibility | Historical Core pending-action/creation-adapter, Flow chat-metadata and Mind Map sync imports remain lightweight re-exports. Annotation's old callable router import aliases the new owner lazily. |
| Tests | Adds Core/GUI/approval/dependency regression coverage. Existing fixtures now construct owner workflows or injected services; UI fixtures use temporary data and appropriate teardown. |
| Documentation | Replaces the architecture map, updates module boundaries and affected FEATURES/FUTURE_UPDATES, adds missing module READMEs and records the approved plan. |
| Repository hygiene | Ignores all `data/` stores and `.pytest_cache/`, including previously uncovered Canvas/Habit data. |

## Existing work preserved in the delivery

This working tree already contained substantial uncommitted feature work when the
cleanup began, and the branch was already three commits ahead of its remote.
The cleanup depends on that source. The delivery therefore includes the existing
Canvas, Mind Map, Memory, Creation, Inner Brain, response-mode, Flow/Habit and GUI
implementations needed to build the complete application. Those earlier feature
additions are not new features introduced by this refactor.

The inventory below compares with the source snapshot taken at the start of the
cleanup, rather than mislabeling all changes since Git HEAD as cleanup work.
Earlier planning/report files unrelated to this cleanup are left as they were.
Runtime records, caches and secrets are excluded from the commit.

## Validation

- **Full regression suite: 336 tests passed** in 75.330 seconds using Python 3.13.5
  with PyQt6 and `QT_QPA_PLATFORM=offscreen`.
- **Isolated regression runs: all 25 modules, 336 tests passed.** The four GUI/Mind
  Map modules also passed together with delayed timer processing (70 tests).
- **`python -m compileall .`: passed**, including the final fixture changes.
- **Independent architecture and final integration reviews: passed**, with no
  blocking findings; final fixture review found no masked assertions/exceptions.
- Core import/routing, owner dependency direction, frozen approval scope, single-use
  dispatch, public Canvas projection validation and shared Habit injection have
  dedicated regression coverage.
- Initial full-suite runs exposed stale fixture contracts and Qt callbacks/timers
  surviving test-window disposal. Test teardown now drains workers and disposes
  detached views before deleting temporary service storage. No production Qt
  behavior was changed to make tests pass.

Reproduce with the project Python environment:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tests -v
python -m compileall .
```

Automated model behavior uses test clients where supplied; this is not a live
Ollama quality assessment. Interactive manual checks below remain unperformed.

## Manual checks

Run `python main.py` from the project root using your Python environment with
PyQt6 installed. For model-backed checks, use your normal local Ollama setup.
Create disposable records named **Cleanup Test**; remove only those records when
finished. These are checks for you to perform, not claims of completed manual testing.

1. **Startup and windows.** Open Flow, dedicated Chats, Code Viewer, Mind Map,
   Canvas and Habit Tracker. Open multiple module windows, switch between them,
   close and reopen one. Expect existing content and view state to remain usable;
   navigation must not create a second Habit data source.
2. **Chat isolation.** Create Cleanup Test A and B with different descriptions.
   Send a distinct message in each, switch chats and edit a title/description.
   Expect each transcript and metadata to stay with its chat. Flow may list chat
   metadata but must not inject their message bodies as normal Flow context.
3. **Response modes.** Try Short, Normal and None in a test chat. Short should
   request a brief answer; None should store the user message without adding an
   assistant response. Restore Normal and verify the next request responds.
4. **Annotations and Code Viewer.** Send `[identity]`, then
   `[metadata][module][amadeus_core][features]`. Expect deterministic content and
   the appropriate panel. Open `amadeus_core/core.py` in Code Viewer; ask about it
   with file context enabled, then disabled. Only the enabled request should use
   the selected file as explicit context. Test annotation suggestions as you type.
5. **Creation and decline.** In a dedicated test chat send
   `[sheet][create] Cleanup Test sheet; scope: chat`. Decline once and verify no
   sheet appears; repeat and approve. Expect one sheet linked to that chat. In
   Flow create another with `scope: global`; expect no accidental active-chat link.
   Repeat with `[memory][save] Cleanup Test decision; scope: chat`.
6. **Approval remains tied to its request.** Review the displayed proposal title,
   scope and fields before accepting. Expect one resulting object, with the scope
   shown in the proposal. Declined requests must not later appear in the owner.
   Automated tests additionally cover replay, tampering, expiry and scope freezing.
7. **Sheets and callable context.** Open the test sheet, edit and save a distinctive
   sentence. Use the sheet annotation picker to select it and append a question.
   Expect the selected sheet to supply the answer context. Confirm the other chat
   does not receive this context simply because the sheet panel was opened.
8. **Materials and exports.** Export a small range from a test chat. Open, preview
   and copy its reference in Materials. Ask about that selected export from the
   other test chat. Expect the chosen exported range to be the primary context;
   merely selecting or previewing the material must not inject it into later messages.
9. **Side Ask and comments.** Select text, ask a temporary side question, and verify
   the main transcript stays unchanged until you explicitly save. Save a comment,
   edit it and remove only that test comment. Expect panels and linked graph
   content to reflect those operations.
10. **Mind Map and synchronization.** Locate the test chat/sheet/memory source
    nodes. Edit a source through the supported source editor, then revisit its
    owning module. Expect the source and graph to agree. Move an ordinary graph
    node and check its position persists. When deleting a disposable source node,
    read the source-deletion option and verify only the chosen test source is removed.
11. **Canvas.** Create a disposable workspace, add two text blocks, connect them,
    edit the connector label and move a block. Save/reopen the workspace. Expect
    text, positions and connector endpoints to survive. Send selected/viewport
    context to AMADEUS and verify its response appears only after successful
    generation. The managed Mind Map projection must remain read-only and must
    not generate duplicate projection loops.
12. **Shared Habit service.** Create a test task in Habit Tracker, then in Flow
    send `/habit show; date: 2026-09-14` (substitute your selected date). Expect
    the task to appear. Send `/habit add task Cleanup Test Flow task; date: 2026-09-14`,
    decline once, then repeat and approve. Refresh the Habit view: only the approved
    task should appear. Complete/delete that test task through the supported controls.
13. **Metadata and process events.** Refresh test-chat metadata and open its data
    panel. Expect generated fields to update without replacing manual fields.
    During a conversation, inspect Process Monitor: actual stages should appear
    in order and end as completed or failed. A failed request must not leave a
    partial completed exchange or a half-applied Canvas response.
14. **Restart.** Close AMADEUS completely, restart and revisit the test chats,
    sheet, memory, Canvas workspace and Habit task. Expect persisted content and
    graph links to remain. Unapproved requests are intentionally process-local.

## Remaining boundaries

- Compatibility service accessors remain for old callers; new UI work should use
  explicit Core routes. Some service contracts still use broad Python types.
- PermissionGuard protects the existing proposal workflow. It is not a general
  filesystem, shell or operating-system permission sandbox.
- Persistence remains distributed among the owning module stores. A future
  cross-owner failure may need transaction compensation; this refactor does not
  introduce a universal transaction manager.
- Reasoning and Skills remain foundation placeholders; no new autonomous action,
  skill runner, plugin loader or general vector index is introduced.
- Live model quality and interactive desktop/restart checks remain manual checks.

## Cleanup file inventory

Paths below are relative to the repository. Added/changed means compared with the
saved pre-cleanup working tree, including files that were already untracked then.

<!-- generated-inventory -->

113 cleanup paths; 84 additional pre-existing source/documentation/test paths preserved in this delivery.

- **Changed:** `.gitignore`
- **Changed:** `AMADEUS_CHANGELOG.md`
- **Changed:** `AMADEUS_FUTURE_IMPLEMENTATIONS.md`
- **Changed:** `README.md`
- **Added:** `amadeus_app/FEATURES.md`
- **Added:** `amadeus_app/FUTURE_UPDATES.md`
- **Added:** `amadeus_app/README.md`
- **Added:** `amadeus_app/__init__.py`
- **Added:** `amadeus_app/composition.py`
- **Changed:** `amadeus_core/FEATURES.md`
- **Changed:** `amadeus_core/FUTURE_UPDATES.md`
- **Changed:** `amadeus_core/README.md`
- **Changed:** `amadeus_core/core.py`
- **Changed:** `amadeus_core/core_coordinator.py`
- **Changed:** `amadeus_core/creation_workspace_adapter.py`
- **Changed:** `amadeus_core/module_registry.py`
- **Added:** `amadeus_core/module_routes.py`
- **Changed:** `amadeus_core/pending_actions.py`
- **Changed:** `amadeus_gui/FEATURES.md`
- **Changed:** `amadeus_gui/FUTURE_UPDATES.md`
- **Changed:** `amadeus_gui/main/main_window.py`
- **Changed:** `annotation_module/FEATURES.md`
- **Changed:** `annotation_module/FUTURE_UPDATES.md`
- **Changed:** `annotation_module/__init__.py`
- **Changed:** `annotation_module/annotation_result.py`
- **Changed:** `annotation_module/annotations/sheet_annotation.py`
- **Changed:** `annotation_module/callable_context_router.py`
- **Added:** `annotation_module/suggestions.py`
- **Changed:** `canvas_module/FEATURES.md`
- **Changed:** `canvas_module/FUTURE_UPDATES.md`
- **Changed:** `canvas_module/canvas_module.py`
- **Changed:** `canvas_module/gui/view.py`
- **Added:** `canvas_module/request_handler.py`
- **Added:** `chat_workspace/FEATURES.md`
- **Added:** `chat_workspace/FUTURE_UPDATES.md`
- **Added:** `chat_workspace/README.md`
- **Added:** `chat_workspace/__init__.py`
- **Added:** `chat_workspace/conversation.py`
- **Added:** `chat_workspace/documents.py`
- **Added:** `chat_workspace/exchanges.py`
- **Added:** `chat_workspace/lifecycle.py`
- **Added:** `chat_workspace/metadata.py`
- **Added:** `chat_workspace/selected_context.py`
- **Changed:** `context_builder/FEATURES.md`
- **Changed:** `context_builder/FUTURE_UPDATES.md`
- **Added:** `context_builder/inferred_context.py`
- **Added:** `context_builder/mindmap_context.py`
- **Changed:** `creation_module/FEATURES.md`
- **Changed:** `creation_module/FUTURE_UPDATES.md`
- **Added:** `creation_module/README.md`
- **Added:** `creation_module/approved_actions.py`
- **Added:** `creation_module/chat_metadata.py`
- **Added:** `creation_module/requests.py`
- **Changed:** `docs/ARCHITECTURE.md`
- **Added:** `docs/CORE_CLEANUP_REPORT.md`
- **Changed:** `docs/MODULE_RULES.md`
- **Added:** `docs/superpowers/plans/2026-09-12-core-ownership-cleanup.md`
- **Added:** `docs/superpowers/specs/2026-09-12-core-ownership-cleanup-design.md`
- **Changed:** `flow_chat/FEATURES.md`
- **Changed:** `flow_chat/FUTURE_UPDATES.md`
- **Changed:** `flow_chat/chat_creation.py`
- **Added:** `flow_chat/request_handler.py`
- **Changed:** `habit_tracker/FEATURES.md`
- **Changed:** `habit_tracker/FUTURE_UPDATES.md`
- **Changed:** `habit_tracker/__init__.py`
- **Added:** `habit_tracker/actions.py`
- **Changed:** `habit_tracker/view.py`
- **Changed:** `inner_brain/FEATURES.md`
- **Changed:** `inner_brain/FUTURE_UPDATES.md`
- **Added:** `inner_brain/README.md`
- **Changed:** `materials_module/FEATURES.md`
- **Changed:** `materials_module/FUTURE_UPDATES.md`
- **Added:** `materials_module/workspace.py`
- **Changed:** `mindmap/FEATURES.md`
- **Changed:** `mindmap/FUTURE_UPDATES.md`
- **Changed:** `mindmap/integrations/workspace_sync.py`
- **Changed:** `permissions/FEATURES.md`
- **Changed:** `permissions/FUTURE_UPDATES.md`
- **Changed:** `permissions/README.md`
- **Changed:** `permissions/__init__.py`
- **Added:** `permissions/guard.py`
- **Added:** `permissions/pending_actions.py`
- **Changed:** `project_file_reader/FEATURES.md`
- **Changed:** `project_file_reader/FUTURE_UPDATES.md`
- **Added:** `project_file_reader/workspace.py`
- **Added:** `response_modes/FEATURES.md`
- **Added:** `response_modes/FUTURE_UPDATES.md`
- **Added:** `response_modes/README.md`
- **Added:** `response_modes/response_payload.py`
- **Changed:** `sheets_module/FEATURES.md`
- **Changed:** `sheets_module/FUTURE_UPDATES.md`
- **Changed:** `sheets_module/sheet_service.py`
- **Changed:** `side_ask_module/FEATURES.md`
- **Changed:** `side_ask_module/FUTURE_UPDATES.md`
- **Added:** `side_ask_module/workflow.py`
- **Changed:** `tests/test_annotation_core.py`
- **Changed:** `tests/test_annotation_gui.py`
- **Added:** `tests/test_architecture_boundaries.py`
- **Changed:** `tests/test_canvas_module.py`
- **Changed:** `tests/test_flow_chat_gui.py`
- **Changed:** `tests/test_flow_habit_commands.py`
- **Changed:** `tests/test_materials_service.py`
- **Changed:** `tests/test_mindmap.py`
- **Changed:** `tests/test_mindmap_annotation.py`
- **Changed:** `tests/test_project_file_reader.py`
- **Added:** `tests/test_workspace_boundaries.py`
- **Added:** `workspace_integration/FEATURES.md`
- **Added:** `workspace_integration/FUTURE_UPDATES.md`
- **Added:** `workspace_integration/README.md`
- **Added:** `workspace_integration/__init__.py`
- **Added:** `workspace_integration/creation_adapter.py`
- **Added:** `workspace_integration/graph_workspace.py`
- **Added:** `workspace_integration/workspace_sync.py`

## Preserved prerequisite paths included in the commit

These files already differed from Git HEAD when cleanup began. Their contents
were preserved; they support the complete application being delivered.

- `amadeus_chat/FEATURES.md`
- `amadeus_chat/chat_module.py`
- `amadeus_gui/README.md`
- `amadeus_gui/approval_dialog.py`
- `amadeus_gui/flow_chat_view.py`
- `amadeus_gui/module_window_manager.py`
- `amadeus_gui/side/side_panel.py`
- `amadeus_trace/trace_logger.py`
- `annotation_module/annotation_context.py`
- `annotation_module/annotation_suggestions.py`
- `annotation_module/annotations/__init__.py`
- `annotation_module/annotations/memory_annotation.py`
- `annotation_module/annotations/metadata_annotation.py`
- `annotation_module/creation_commands.py`
- `annotation_module/flow_command_suggestions.py`
- `canvas_module/README.md`
- `canvas_module/__init__.py`
- `canvas_module/context.py`
- `canvas_module/conversation.py`
- `canvas_module/models.py`
- `canvas_module/storage.py`
- `comments_module/FEATURES.md`
- `comments_module/FUTURE_UPDATES.md`
- `comments_module/comment_entry.py`
- `comments_module/comment_service.py`
- `comments_module/comment_store.py`
- `context_builder/chat_context_builder.py`
- `creation_module/__init__.py`
- `creation_module/errors.py`
- `creation_module/habit_tasks.py`
- `creation_module/interfaces.py`
- `creation_module/models.py`
- `creation_module/ollama_json_adapter.py`
- `creation_module/service.py`
- `creation_module/workspace_models.py`
- `flow_chat/__init__.py`
- `flow_chat/flow_chat_service.py`
- `flow_chat/flow_context_builder.py`
- `flow_chat/habit_commands.py`
- `flow_chat/habit_request_service.py`
- `flow_chat/review_context_builder.py`
- `habit_tracker/README.md`
- `habit_tracker/service.py`
- `inner_brain/__init__.py`
- `inner_brain/models.py`
- `inner_brain/service.py`
- `llm_client/ollama_client.py`
- `memory_module/FEATURES.md`
- `memory_module/FUTURE_UPDATES.md`
- `memory_module/__init__.py`
- `memory_module/creation_adapter.py`
- `memory_module/memory_service.py`
- `memory_module/memory_store.py`
- `memory_module/mindmap_projection.py`
- `memory_module/models.py`
- `memory_module/repository.py`
- `memory_module/vector_store.py`
- `mindmap/README.md`
- `mindmap/__init__.py`
- `mindmap/gui/__init__.py`
- `mindmap/gui/items.py`
- `mindmap/gui/physics.py`
- `mindmap/gui/view.py`
- `mindmap/integrations/__init__.py`
- `mindmap/mind_map_module.py`
- `mindmap/models.py`
- `mindmap/service.py`
- `project_file_reader/project_file_reader.py`
- `response_modes/__init__.py`
- `response_modes/response_policy.py`
- `storage/__init__.py`
- `storage/chat_history_store.py`
- `tests/test_annotation_creation_commands.py`
- `tests/test_chat_history_store.py`
- `tests/test_comments_module.py`
- `tests/test_creation_module.py`
- `tests/test_flow_chat.py`
- `tests/test_habit_tracker.py`
- `tests/test_inner_brain.py`
- `tests/test_memory_foundation.py`
- `tests/test_mindmap_workspace_sync.py`
- `tests/test_module_metadata_annotation.py`
- `tests/test_pending_actions.py`
- `tests/test_response_modes.py`
