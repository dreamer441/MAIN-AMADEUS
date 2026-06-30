# AMADEUS Chat Features

- Receives normal chat messages from Core.
- Builds a simple user prompt for the LLM client.
- Accepts optional read-only project context from Core.
- Accepts optional AMADEUS identity context from Core.
- Combines stable chat safety rules with the global Identity Module prompt.
- Sends prompts to the configured LLM client.
- Returns clear errors when Ollama cannot respond.


- Receives recent conversation context from Core/Context Builder so AMADEUS can refer back to earlier messages in the current chat.
- Receives project context separately from conversation context, keeping prompt sections clearer.
