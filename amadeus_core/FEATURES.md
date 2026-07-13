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
- Core can create chats with title and description through Storage.
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
