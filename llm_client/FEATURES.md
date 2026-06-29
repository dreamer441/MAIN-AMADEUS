# LLM Client Features

- Connects to Ollama at `http://localhost:11434`.
- Uses `llama3.2:latest` as the default lightweight model.
- Sends non-streaming prompts to Ollama.
- Provides a basic health check.
- Returns readable errors for missing Ollama or missing model setup.
