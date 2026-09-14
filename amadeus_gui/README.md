# AMADEUS GUI

The GUI is the desktop surface for AMADEUS.

It sends user messages to Core and displays:

- AMADEUS chat response
- latest Process Monitor trace

The GUI does not decide routing. Core decides where a message goes and sends the response plus trace data back to the GUI.

The Process Monitor is diagnostic only. It shows real execution events, not private hidden thinking.

For normal chat, Process Monitor renders safe structured event rows as Core emits
them through the background worker. When the request completes, the final Core
payload replaces that incremental view so the monitor reflects the authoritative
completed trace. GUI event signals are an adapter only: Core's listener contract
and the trace emitter remain framework-independent. Annotation, material, and
other non-normal-chat paths continue to update from their final payloads.

## Package Boundaries

- `amadeus_gui.main` owns the permanent Flow Chat window and cross-window coordination.
- `amadeus_gui.module_window_manager` owns reusable top-level window lifecycle for major modules.
- `amadeus_gui.side` owns the tabbed right-side workspace rendering.
- The GUI continues to call Core public methods only; it does not read or write module storage directly.

## Right Panel and Input Update

The right side of the window is now a tabbed work panel. Process Monitor shows real execution events. Code Viewer shows exact read-only content opened by `[file]`. The input box supports multiline prompts with Shift+Enter and uses `/` to begin guided annotation suggestions.

## Memory Panel

The right panel now includes a Memory tab. `[memory][list]` and save actions update this tab so saved context can be inspected without filling the main chat transcript.

## Flow Home and Independent Module Windows

Flow Chat remains permanently mounted in the primary AMADEUS window with its own transcript, input, and event-only Process Monitor. The sidebar no longer replaces Flow with stacked pages. Instead, Chats, Code, Mind Map, Canvas, and Habit Tracker open as independent top-level windows, allowing several workspaces to stay visible in parallel.

`ModuleWindowManager` creates at most one window for each module, raises/focuses it when reopened, and preserves the exact existing view instance while the window is closed or hidden. This prevents duplicate Canvas, Mind Map, or Chats state. Closing one module leaves Flow and all other modules running; closing Flow coordinates final application shutdown.

The Chats window retains New Chat and Edit Chat dialogs for title, description, priority, purpose, and descriptive V1 scope. Flow and every module window continue to use the same Core instance; the GUI never reads module storage directly.

## Canvas window

The Canvas launcher opens the persistent `CanvasView` supplied by `canvas_module.gui` in its own top-level window. It supports multiple lightweight project workspaces plus typed movable blocks, semantic lines/arrows, root and target-focused context controls, an optional instruction field, and `Send Changes to AMADEUS`. Requests run on a background worker through Core; successful responses appear as movable AMADEUS blocks with saved source arrows, while failed or stale requests leave the Canvas unchanged.
