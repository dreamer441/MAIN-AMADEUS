# AMADEUS Sheets Module

Sheets are editable side-panel documents for AMADEUS.

They are designed as clean information feeders for future Mind Map / Relevance Graph work. A sheet can hold feature notes, project rules, plans, draft text, code notes, decisions, or temporary working context without turning normal chat into permanent memory.

## Current purpose

- Let Dato create editable text sheets in the right-side panel.
- Support two scopes:
  - `chat`: visible only inside the active chat workspace.
  - `global`: visible across chats.
- Let `[sheet]` open/list sheets in the right panel.
- Let `[sheet][scope][title] prompt` inject one selected sheet as callable context for one LLM request.

## Boundary

Sheets are not raw chat history.
Sheets are not global memory.
Sheets are not automatic Mind Map nodes yet.

They are deliberate workspace documents that can later become callable references, exported materials, or Mind Map source nodes.
