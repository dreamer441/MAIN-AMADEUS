# LLM Client Features

- Optional per-client JSON response format and temperature support structured advisory tasks. Defaults remain ordinary text generation at temperature 0.7; application composition configures Inner Brain separately.

## Implemented Now

- Connects to Ollama at `http://localhost:11434`.
- Uses `llama3.2:latest` as the default lightweight model.
- Sends non-streaming prompts to Ollama.
- Supports a separate system prompt for stable AMADEUS rules and identity.
- Provides a basic health check.
- Returns readable errors for missing Ollama or missing model setup.
- Contains comments explaining why model access stays behind one replaceable boundary.
