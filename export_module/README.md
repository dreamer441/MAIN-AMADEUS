# AMADEUS Export Module

The Export Module turns saved chats into stable reference materials.

It exports chats in three formats:

- `.txt` for human viewing in the Materials panel.
- `.md` for readable future AMADEUS context.
- `.json` for exact message-number retrieval and future tools.

Exports are callable context, not active memory. They are only injected into the LLM when Dato explicitly uses `[export]` with prompt text.

## Clear annotation structure

Preferred structured forms:

```text
[export]                         # export/open current chat
[export][list]                   # show exported chats in Materials
[export][open][Chat Title]       # open/export a named chat
[export][open][Chat Title][4-6]  # open selected messages in Materials
[export][use][Chat Title][4-6] explain this segment
```

The older shorthand still works:

```text
[export][Chat Title][4-6] explain this segment
```

## Context accuracy rule

When an export range is used as callable context, Core deliberately does **not** inject the current chat transcript. The selected exported messages are labeled as real exported chat text, not metadata, so AMADEUS should answer from that exact exported segment instead of drifting back to the current conversation.
