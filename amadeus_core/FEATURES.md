# AMADEUS Core Features

- Registers built-in modules through `ModuleRegistry`.
- Routes normal messages to `amadeus_chat`.
- Routes bracket annotations through `annotation_module`.
- Registers the Identity module as a global project module.
- Uses `context_builder` to select recent chat history and project context before chat.
- Starts a new `amadeus_trace` session for every user message.
- Returns both AMADEUS response text and Process Monitor trace data to the GUI.
- Persists completed user/AMADEUS exchanges through local chat history storage.

Core rule:

> Core routes. Modules execute. Context Builder selects context. Trace records real execution events.
