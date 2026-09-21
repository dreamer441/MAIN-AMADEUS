# Inner Brain Features

- Uses an injected local `nemotron-3-nano:4b` client and never alters the primary chat client.
- Requests strict JSON only and validates bounded read annotation, metadata, summaries, and advisory write candidates.
- Returns an empty safe analysis for model, JSON, or schema failures.
- Has no persistence, filesystem, export, or Mind Map access.
- Chat and Flow consume one advisory analysis per plain request. Context Builder supplies verified module listings and bounded sheet/export/graph inventories; explicit commands bypass inference. Creation candidates create only registered pending actions and never execute before approval.
- For plain general chat only, can advisory-classify verified module metadata requests as `open` or `answer` with an allow-listed module and document kind. Flow Chat never infers module metadata.

## Core ownership cleanup — 2026-09-12

- Implemented: Advisory analysis remains pure. Application setup injects it into Context Builder and dedicated-chat metadata workflows; it owns no execution or storage.

## Reliability repair — 2026-09-21

- The secondary client requests JSON with thinking disabled, temperature zero, and a 30-second HTTP timeout. Primary chat settings remain unchanged.
- Intent and summary generation use separate prompts and budgets (300 and 700 output tokens). Long transcript summaries retain the beginning and latest messages, with the omitted middle marked.
- Valid no-intent results are distinct from model/JSON/schema failures. Chat and Flow show safe analysis status in Process Monitor and continue normal answering on advisory failure.
- Invalid metadata targets cannot silently expand into all-module requests. Documentation intent must be grounded in documentation wording. Unknown fields and invalid value types are rejected.
- Failed, incomplete, or empty-chat refreshes preserve previously saved Chat Data. Manual title and description remain protected.
- Deterministic regression tests and opt-in local-model tests cover routing, failure behavior, non-mutation, and synthetic intent/summary quality.
