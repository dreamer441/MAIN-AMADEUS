# AMADEUS Chat Features

## Implemented Now

- Receives normal chat messages from Core.
- Builds a stable prompt for the LLM client.
- Accepts optional recent conversation context from Core/Context Builder so AMADEUS can refer back to earlier messages in the current chat.
- Accepts optional read-only project context from Core/Context Builder.
- Accepts optional AMADEUS identity context from Core.
- Combines stable chat safety rules with the global Identity Module prompt.
- Includes strict file/folder honesty rules in the system prompt: use only verified Project File Reader context and never invent file names, folder contents, module names, or code facts.
- Sends prompts to the configured LLM client.
- Returns clear errors when Ollama cannot respond.
- Records real LLM boundary trace events when Core provides a trace logger.
- Uses `LLM Request` and `LLM Response` titles with safe operational summaries only; prompts and responses are not included in trace data.
- Contains comments explaining why Chat formats prompts but does not own routing, storage, GUI, or file reading.

## Normal Chat File Boundary

- Normal chat may summarize or explain AMADEUS modules from overview context.
- Normal chat should not claim to open exact files or quote exact file contents.
- Exact verified file access is intentionally moved to `[file]` so code/folder facts come from Python, not LLM guesses.

## Memory-Aware Prompting

- Normal chat now accepts memory context from Context Builder.
- The prompt separates recent conversation, project overview, and explicit saved memory.
- Memory is presented as durable context, not as a new user instruction.


## Chat Workspace Context

- Normal chat prompts can now include the active chat title/description.
- Chat workspace context is separated from recent conversation and explicit memory.
- Recent conversation lines can include visible message numbers to support future message references.

## Callable Context

- Chat prompt builder now accepts optional callable context.
- Callable context is currently used by `[sheet][scope][title] prompt`.
- Callable context is separate from memory and recent conversation: it is injected only when Dato explicitly asks through an annotation.

## Callable Context Priority

- Chat prompt construction now tells the LLM that callable context selected by annotations is the primary source for that request.
- This especially protects `[export][use][chat][range] prompt` from being overridden by current-chat assumptions.
