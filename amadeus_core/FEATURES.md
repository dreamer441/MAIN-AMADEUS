# AMADEUS Core - Current Features

## Purpose
AMADEUS Core is the lightweight coordinator. It routes user messages to the correct module and keeps high-level ownership clean.

## Implemented features

- Creates and registers core modules at startup.
- Routes annotation messages before normal chat.
- Routes normal messages to the Chat Module.
- Uses Context Builder for recent conversation and project overview context.
- Injects AMADEUS global identity into normal chat through the Identity Module.
- Persists user/AMADEUS exchanges through Storage.
- Exposes multi-chat methods for GUI: list chats, create chat, delete chat, switch chat, load active chat history.
- Keeps the active chat inside Storage, so Context Builder uses only the selected chat's history.
- Creates one Process Monitor trace session per user message.
- Owns normal-chat request receipt, route selection, and terminal lifecycle events.
- Returns response text, trace text, and optional side-panel payloads to the GUI.
- Routes exact file access through annotations, especially `[file]`; normal chat remains summary/explanation mode.

## Routing order

1. Input received
2. Annotation check
3. Annotation route if detected
4. Normal chat route
5. Context Builder selects active-chat history and safe project overview context
6. Chat Module calls the LLM client
7. Output returned to GUI

## Shared Process Events

- Normal active-chat events are one ordered lifecycle: request receipt, declared route work plan, actual Context Builder source loads, configured-LLM response composition, completed-exchange storage, and Core terminal result.
- Core records only its own request-routing and terminal boundaries; it does not expose prompt or selected context values in trace metadata.
- Side Ask and annotation/callable-context routes declare their observable intent and retain their own no-persist or completed-persistence boundary.
- A failed Chat event or missing Chat registration produces `Request Failed` while preserving the established user-facing error response.

## Flow Chat Routing

- Core composes and registers isolated Flow storage, Flow context building, Flow service, and metadata-only dedicated-chat registry modules.
- `handle_flow_message()` reuses the shared Chat module, LLM client, identity prompt builder, and Process Monitor event stream without changing normal chat routing.
- Flow context contains only recent Flow history and `[AVAILABLE DEDICATED CHATS]` metadata; dedicated-chat message bodies are never loaded or injected.
- Successful Flow exchanges persist as one atomic two-message update under `data/flow_chat`; failed Flow execution leaves no partial exchange and returns a generic safe failure response.
- Flow emits the same ordered, safe shared Process Monitor events to a live listener and the final response payload; event rows describe execution boundaries only and contain no prompt, response, or dedicated-chat body content.
- The registry reads current dedicated-chat metadata on each Flow context build, so live create, title/description/priority/purpose/scope updates, and delete mutations are reflected without Flow owning a second index.

## Mind Map Routing

- Core constructs and registers `MindMapModule` as `mind_map`.
- Core exposes snapshot, CRUD, move, search, bounded-neighborhood, JSON import/export, source-upsert, and live-subscription wrappers.
- The Mind Map GUI calls these wrappers only; Core does not implement graph storage, layout, or source-adapter policy.
- Mind Map mutation events are real ordered operation boundaries with generic summaries and generic failed terminals that exclude graph content, labels, user errors, backend details, and hidden reasoning.
- Mind Map subscriptions are redacted invalidation notices containing only operation/entity identifiers, graph ID, and timestamp; consumers retrieve graph details through Core snapshots.
- Core registers `[mindmap]` and injects the `MindMapModule` facade into Annotation Module's callable-context router. Prompt-bearing Mind Map annotations retrieve through `search_nodes()` or SQL-bounded `list_recent_nodes()` only, never through SQLite.
- Mind Map query events report started, retrieved, no-match, or failed boundaries with generic summaries; node values, query text, and backend errors remain out of Process Monitor events.

## Important boundary

Core routes. It should not become a place for large feature logic. If Core starts growing too much, the logic should move into a module such as Context Builder, Project File Reader, Annotation Module, or Storage.

## Annotation-First File Access Routing

- Core no longer treats natural-language file reads as exact filesystem commands.
- Exact file access is routed through annotations, especially `[file]`.
- Core can return optional side-panel payloads from annotations to the GUI.
- Core exposes read-only annotation suggestions for the GUI command builder.

## Multi-Chat Boundary

- Core exposes chat-management methods, but Storage owns chat metadata and chat files.
- Core should not format chat selector UI or directly inspect chat JSONL files.
- Chat switching affects future persistence and Context Builder history selection.

## Memory V1 Integration

- Core now creates and registers `memory_module`.
- Core registers `[memory]` as a structured annotation handler.
- Core passes MemoryService into AnnotationContext and Context Builder.
- Core traces memory annotation handling and memory context injection.


## Chat Workspace V2 Integration

- Core exposes current chat metadata to the GUI.
- Core creates and updates validated title, description, priority, purpose, and scope chat metadata through Storage.
- Core passes chat workspace context selected by Context Builder into the Chat module.
- Process Monitor records when chat workspace context is injected.

## Side Panel Foundation Compatibility

- Core still returns optional `side_panel` payloads in response dictionaries.
- Side-panel rendering/state now belongs to the GUI/right-panel layer and `side_panel` module, not Core.
- This keeps Core focused on routing and payload delivery instead of GUI layout details.

## Sheets / Materials Routing

- Core now owns `SheetService` and `MaterialsService` instances.
- Core registers `sheets` and `materials` modules.
- Core registers `[sheet]` annotation handler.
- Core supports the hybrid route `[sheet][scope][title] prompt`, loading exact sheet content and passing it to normal chat as callable context.
- Core exposes sheet create/update/delete and panel payload methods for the GUI.

## Export Routing

- Core now registers `export_module` and `[export]` annotation handling.
- Core can route `[export][chat][range] prompt` to normal chat with callable export context.
- Core returns Materials panel payloads for export display.

## Export Scope Lock

- Export prompt requests now intentionally skip current chat transcript/workspace injection.
- This prevents `[export][chat][message] prompt` from answering from the active chat instead of the selected exported chat segment.
- Core still allows saved memory context, but the selected export block becomes the primary source for the request.

## Phase 5 Materials Routing

- Core exposes list, preview, open, reference-copy, removal, and explicit material-message routes.
- Core delegates every Materials action to `MaterialsService`; the GUI does not read material or export storage.
- `handle_material_message()` creates callable context for exactly the selected request. Selection and opening alone never inject context.

## Side Ask / Comments Routing

- Core exposes `handle_side_ask()` for temporary side questions.
- Side Ask uses selected text as callable context but does not persist automatically.
- Core exposes `save_side_ask_to_chat()` for explicit transcript insertion.
- Core exposes comment save/list payload methods through `comments_module`.

## Phase 2 Callable Annotation Routing

- Core delegates callable `[sheet]` and `[export]` prompt handling to `annotation_module.CallableContextRouter`.
- The Annotation Module now resolves the selected stored object, builds callable context, and preserves the export scope lock through module public APIs.
- Core supplies routing callbacks, trace delivery, and persistence coordination without implementing sheet/export selection details in the active request path.

## Phase 3 Annotation Block Routing

- Core consumes parser-owned annotation blocks without scanning for block syntax.
- It executes blocks in source order through the annotation registry.
- With text outside blocks, Core sends only that text to Chat and injects combined deterministic block results as callable context.
- With block-only input, Core returns the deterministic results together without calling the LLM.
- An unclosed single leading annotation retains the established legacy callable sheet/export route.

## Phase 4 Project File APIs

- Core exposes project-root tree navigation and file-open APIs while delegating every filesystem operation to Project File Reader.
- Core asks about a selected file directly and adds file context only when the caller explicitly enables it.
- Enabled file context is verified, line-labelled, range-limited when requested, and never saved as memory or automatically injected into later requests.


## Canvas Foundation Routing

- Core creates and registers the first-class `canvas` module facade.
- Core exposes safe Canvas workspace metadata to the GUI without importing PyQt scene internals.
- Canvas remains a separate module boundary prepared for future structured objects, persistence, context extraction, and AMADEUS response routing.
