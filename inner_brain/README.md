# Inner Brain

Performs bounded advisory JSON analysis through an injected model client. It never accesses storage or executes suggested actions. Context Builder resolves permitted read hints; Creation and Permissions handle proposals.

## Files

service.py validates advisory analysis; models.py defines the bounded records.

See `docs/ARCHITECTURE.md` for cross-module ownership.

The configured secondary client uses local `nemotron-3-nano:4b`, JSON format,
thinking disabled, temperature zero, and a 30-second HTTP timeout. Its intent
analysis and explicit chat-summary refresh are separate tasks. `succeeded` and
the safe `error` code distinguish a valid no-intent result from failed analysis.
Conversation owners show failure status; Chat Metadata preserves the previous
successful record if a refresh is empty, invalid, or incomplete.

Run deterministic checks with `python -m unittest discover -s tests -p test_inner_brain.py`.
For synthetic live-model checks, set `AMADEUS_RUN_LIVE_MODEL_TESTS=1` and run
`python -m unittest discover -s tests -p test_inner_brain_live.py -v`.
The live checks require Ollama and the installed Nemotron model and never read
user chats or write application data. They are a small smoke suite, not an accuracy benchmark.
