# AMADEUS Chat Module

The Chat module owns normal conversation behavior.

Chat does not read files, control the GUI, or decide global identity. Core provides any relevant context, and Chat sends that context to the LLM client through one stable prompt shape.

The Identity Module is injected through Core so AMADEUS responds from her global identity without hardcoding the full charter inside Chat.
