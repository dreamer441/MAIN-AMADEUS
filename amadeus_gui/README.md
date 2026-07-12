# AMADEUS GUI

The GUI is the desktop surface for AMADEUS.

It sends user messages to Core and displays:

- AMADEUS chat response
- latest Process Monitor trace

The GUI does not decide routing. Core decides where a message goes and sends the response plus trace data back to the GUI.

The Process Monitor is diagnostic only. It shows real execution events, not private hidden thinking.

## Right Panel and Input Update

The right side of the window is now a tabbed work panel. Process Monitor shows real execution events. Code Viewer shows exact read-only content opened by `[file]`. The input box supports multiline prompts with Shift+Enter and uses `/` to begin guided annotation suggestions.

## Memory Panel

The right panel now includes a Memory tab. `[memory][list]` and save actions update this tab so saved context can be inspected without filling the main chat transcript.
