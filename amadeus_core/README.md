# AMADEUS Core

`amadeus_core` is the lightweight coordinator for the AMADEUS shell.

Core is responsible for:

- registering modules
- checking annotations
- routing messages
- requesting selected context from Context Builder
- preparing identity prompt injection
- creating a Process Monitor trace session for each message
- returning the final response payload to the GUI

Core is not responsible for generating LLM responses, reading every file directly, or owning feature-specific behavior.

The current `handle_user_message()` response shape is:

```python
{
    "response": "AMADEUS response text",
    "trace": "compact trace text",
    "trace_detailed": "detailed trace text",
    "trace_events": [],
}
```

The trace data represents real execution events only. It must not be used to invent or display hidden chain-of-thought.

## Memory V1 Role

Core owns only the routing: it registers `memory_module`, routes `[memory]` annotations, and passes memory context into Context Builder/Chat. Memory save/list logic stays inside `memory_module`.
