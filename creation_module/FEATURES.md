# Creation Module Features

## Implemented

- Orchestrates metadata generation, source categorization, temporary memory proposals, and explicit proposal approval.
- Uses the existing Ollama `generate` client through strict JSON parsing and typed validation.
- Preserves manual metadata fields unless a caller explicitly requests replacement.
- Rechecks the raw-source hash before every metadata, categorization, and approved-memory write.
- Has no database, JSONL writes, autonomous loop, model routing, or GUI view.
- Validates immediate Sheet, Comment, and Memory requests for explicit Flow commands.
- Sends validated requests through one Core-composed owner adapter; owner services persist records and Mind Map workspace sync runs after persistence. The default scope is global/unlinked, and only the exact final `; scope: chat` suffix supplies the current chat owner.
- Prepares non-empty typed Habit Tracker task proposals for Flow; it never writes
  the Habit Tracker database.

## Boundaries

- Raw source content is supplied only at registration by an owning caller. Creation never reads a locator or arbitrary filesystem path.
- Memory Module owns all source metadata and Memory Brick persistence.
- Only `create_approved_memory_bricks()` can create memory, and only for supplied approved proposal IDs.
- Immediate workspace requests never create Canvas or Mind Map records directly. Mind Map projection is a Core callback after the owner record exists.

## Core ownership cleanup — 2026-09-12

- Implemented: CreationRequestService prepares fixed-scope proposals for PermissionGuard. ApprovedCreationActions delegates to owner services. Shared chat metadata resolution lives here with the old Flow import retained.
