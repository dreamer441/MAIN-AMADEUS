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

## Flow Route

`handle_flow_message()` is a separate Core route for the Flow home conversation. It uses the shared Chat module, identity prompt builder, and Process Monitor event lifecycle while leaving normal dedicated-chat routing unchanged. Flow history is loaded and persisted through `flow_chat` under `data/flow_chat/`, separately from `data/chats/`.

Flow context has two isolated layers: Layer 0 is recent Flow history; Layer 1 is current dedicated-chat registry metadata. The registry projects only `chat_id`, title, and description and reads no dedicated-chat message bodies. Its list is evaluated when Flow builds context, so dedicated-chat create, metadata-update, and delete mutations are reflected without duplicating registry state.

## Memory V1 Role

Core owns only the routing: it registers `memory_module`, routes `[memory]` annotations, and passes memory context into Context Builder/Chat. Memory save/list logic stays inside `memory_module`.
