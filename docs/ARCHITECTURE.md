# AMADEUS architecture

AMADEUS is a modular, local-first desktop companion. This map describes the
implemented ownership boundaries as of 2026-09-14.

## Startup and requests

Application composition in `amadeus_app/composition.py` constructs the dependency
graph once. Core resolves named owners and exposes explicit routes:

```text
main.py -> AmadeusCore -> application composition (startup only)
GUI -> Core route -> owner workflow -> public owner services -> stores / LLM client
GUI <- response and real execution events <- owner workflow
```

Importing Core does not import feature implementations or Qt. A registry can be
injected for routing tests without starting the application or creating data.

## Ownership map

| Owner | Responsibility and internal components |
|---|---|
| `amadeus_core` | Registry, explicit request forwarding, Canvas/Habit routing facades; compatibility exports contain no execution |
| `amadeus_app` | Startup composition and explicit dependency injection |
| `chat_workspace` | Dedicated-chat conversation, selected-context execution, lifecycle, metadata, documents and exchange persistence |
| `amadeus_chat` | Prompt construction and generation using supplied context and the LLM client |
| `flow_chat` | Isolated Flow request handler, service, store, context, review and Habit command handling |
| `annotation_module` | Parser, registry, syntax interpretation, deterministic handlers and suggestions |
| `context_builder` | Context selection, bounded inferred reads, literal Mind Map context formatting |
| `identity_module` | Global identity, charter and identity prompts |
| `inner_brain` | Bounded advisory model analysis; no persistence or action execution |
| `creation_module` | Metadata generation, shared chat metadata resolver, proposal preparation, approved creation through public owners |
| `permissions` | Pending records and PermissionGuard with registered owner callbacks |
| `workspace_integration` | Source synchronization, graph workflow and creation adapter across owners |
| `mindmap` | Graph facade, validation service, repository, models and visualization |
| `canvas_module` | Spatial conversation facade, stores, context, generation, request handler and GUI |
| `habit_tracker` | Shared task/calendar/alarm service, approved-action executor and optional GUI |
| `memory_module`, `sheets_module`, `comments_module` | Own their records, services and persistence |
| `materials_module`, `export_module` | Managed references, exports and explicit selected-context adapter |
| `side_ask_module` | Temporary secondary question workflow and explicit transcript saves |
| `project_file_reader` | Verified read-only access, indexing and Code Viewer workspace adapter |
| `response_modes` | Fixed policies, resolver and response/completion presentation |
| `chat_registry` | Dedicated-chat metadata projection for Flow |
| `amadeus_trace` | Real execution events, logger and process emitter |
| `amadeus_gui`, `side_panel` | Windows, workers, widgets and display state |

## Core routes; modules execute

Core does not parse annotations, construct prompts, generate chat metadata,
persist exchanges or implement approval policies. Existing public request methods
forward to their registered owners. Canvas and Habit views use `core.canvas` and
`core.habits`; both resolve the same services used by conversation requests.
Legacy Core service accessors remain for integrations. New GUI code uses routes.

## Submodules extend their owners

Implementation helpers live under their owning module. Application setup may
construct these helpers; request-time consumers use public interfaces. Multi-owner
synchronization belongs in `workspace_integration`, not inside Mind Map or Core.
Sheets accepts plain scope/reference values and does not import Annotation types.
The old selected-context router import is a compatibility export; its actual
conversation execution belongs to Chat Workspace. Module view/model imports are
presentation composition, not permission to call raw feature services from GUI.

## Storage stores

Persistence is module-owned rather than one universal database. `storage` owns
dedicated-chat JSONL and metadata. Flow owns separate JSONL. Sheets/comments own
their records; Memory retains legacy JSONL plus structured SQLite. Mind Map and
Habit own SQLite databases; Canvas owns documents and a workspace registry.
Core, GUI and Creation do not write these stores directly. All `data/` contents
are local runtime data and excluded from Git.

## PermissionGuard protects existing proposals

Chat, sheet, comment, memory, export and Habit proposals use expiring single-use
records. Scope is captured before approval. Decline never invokes an owner;
approval consumes the request before dispatch, including when the owner fails.
Existing direct user edits continue through owner validation. This guard is not
a general filesystem, shell or operating-system sandbox.

## Foundations still pending

`reasoning_module` and `skills` remain deliberate placeholders. Inner Brain is
advisory analysis, not a full reasoning engine. A general skill runner, plugin
loader, capability permissions and vector index remain future work. No autonomous
memory saving or project editing is introduced by this cleanup.

See `CORE_CLEANUP_REPORT.md` for the change inventory and manual checks.
