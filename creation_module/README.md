# Creation Module

Generates source metadata and proposals; prepares explicit creation requests and executes approved requests through injected public owners. It owns no local stores.

## Files

service.py and interfaces.py define creation; requests.py prepares approval; approved_actions.py dispatches approved creation; chat_metadata.py holds the shared chat resolver; adapters and models support these workflows.

See `docs/ARCHITECTURE.md` for cross-module ownership.
