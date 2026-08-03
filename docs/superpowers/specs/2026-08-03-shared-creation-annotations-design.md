# Shared Creation Annotations Design

## Purpose

Make the Annotation Module the single command contract for Flow and dedicated
AMADEUS chats. Sheet and Memory creation must extend their existing annotations,
and chat creation must be available from both conversation surfaces. The only
confirmation surface is the GUI approval dialog; transcript text must not ask
the user to approve an action.

## Shared Annotation Routing

Core parses supported annotations before routing a request to either Flow's
normal LLM conversation or dedicated-chat's normal LLM conversation. Both
surfaces receive the same annotation suggestions and execute the same supported
annotation forms:

- `[file]`, `[sheet]`, `[memory]`, `[export]`, `[identity]`, and `[mindmap]`
- `/create-chat <request>` for dedicated-chat creation

The Annotation Module owns command parsing, suggestions, and typed creation
request preparation. Core retains ownership of pending actions, owner-service
calls, and Mind Map synchronization. Flow and GUI code do not access storage.

## Sheet And Memory Creation

`[sheet]` remains the Sheet annotation and gains a guided creation form. Its
existing listing, scoped selection, and callable-context forms remain unchanged.

`[memory]` remains the Memory annotation and gains a guided save form. Its
existing listing and scope forms remain unchanged.

The old `/create-sheet` and `/create-memory` commands are removed. New Sheet
and Memory creation is expressed through `[sheet]` and `[memory]` only.

## Creation Intent And Approval

Inner Brain performs bounded advisory intent detection for plain-language
requests in both Flow and dedicated chats. Its allowed targets are `chat`,
`sheet`, and `memory`, and its generated title and description are display
defaults only. It does not issue commands, select storage identifiers, or write
data.

Core converts a validated intent or explicit creation annotation into a
process-local pending action. The response exposes `approval_request` to the
GUI but contains no visible approval instruction. The GUI immediately presents
the reusable approval dialog, pre-filled with safe action fields.

Approve consumes the single-use Core pending action and routes it through the
existing owner facade. Decline discards it. Both paths produce a local outcome
message after the dialog closes. No owner record is written before approval.

## Scope And Mind Map Links

Flow-created Sheets and Memory default to global scope with no linked chat. The
Mind Map workspace sync creates their source nodes without a chat relationship.

Dedicated-chat-created Sheets and Memory default to the current chat scope and
use that current chat as the linked chat ID. Workspace sync creates their source
nodes and the relationship to that chat.

An explicit supported scope override is authoritative. A Flow request can opt
into chat scope, and a dedicated-chat request can opt into global scope.

Chat creation is not linked to the requesting chat.

## GUI Updates

Both Flow and dedicated-chat inputs request common annotation suggestions from
Core. Dedicated chat refreshes its selector, workspace panels, and linked Mind
Map panel after approval. Flow refreshes the relevant global panels and Mind Map
view after approval, without selecting or linking a dedicated chat.

## Errors And Tests

Malformed annotations, unsupported creation targets, missing creation content,
expired actions, and invalid approval IDs return safe local errors without
persistence. The dialog is not shown for malformed requests.

Tests cover shared suggestions and routing, existing annotation preservation,
explicit and inferred chat/sheet/memory creation, dialog-only approval output,
Flow standalone Mind Map nodes, dedicated-chat source links, scope overrides,
decline behavior, and post-approval UI refresh hooks.
