# AMADEUS Trace Module

`amadeus_trace` provides the first AMADEUS Process Monitor foundation.

It records structured execution events that actually happen while AMADEUS handles one user message. It is not a hidden-thinking viewer and must never invent private reasoning or fake chain-of-thought.

The trace flow is simple:

1. Core creates a new trace session for the user message.
2. Core and modules add real events such as input received, annotation check, routing decision, LLM call, errors, and output ready.
3. The GUI displays the latest trace in the Process Monitor panel.

Trace sessions are per-message so the latest monitor view stays focused and does not mix old routing events with the current request.
