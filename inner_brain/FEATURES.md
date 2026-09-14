# Inner Brain Features

- Uses an injected local `nemotron-3-nano:4b` client and never alters the primary chat client.
- Requests strict JSON only and validates bounded read annotation, metadata, summaries, and advisory write candidates.
- Returns an empty safe analysis for model, JSON, or schema failures.
- Has no persistence, filesystem, export, or Mind Map access.
- Core can inject its safe no-argument read-handler result into plain Flow requests; Flow commands bypass inference. Plain dedicated-chat write candidates can create only registered Core pending actions and never execute before GUI approval.
- For plain general chat only, can advisory-classify verified module metadata requests as `open` or `answer` with an allow-listed module and document kind. Flow Chat never infers module metadata.

## Core ownership cleanup — 2026-09-12

- Implemented: Advisory analysis remains pure. Application setup injects it into Context Builder and dedicated-chat metadata workflows; it owns no execution or storage.
