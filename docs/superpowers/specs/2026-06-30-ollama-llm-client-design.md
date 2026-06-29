# Ollama LLM Client Design

Date: 2026-06-30

## Goal

Connect the AMADEUS modular shell to a local Ollama model while preserving the current architecture:

```text
GUI -> Core -> Chat Module -> LLM Client -> Ollama
```

The first LLM integration should replace the Chat module's placeholder response with a real local model response when Ollama is available.

## Hardware Context

The target machine has:

- GPU: RTX 4080 Super
- CPU: Intel i9 14th generation
- RAM: 64 GB
- Storage: 1 TB / 4 TB SSD

The user prefers answer quality over speed.

## Model Choice

Use `qwen3:32b` as the default Ollama model.

Reasons:

- Strong general chat and reasoning performance.
- Suitable for a high-end desktop with 64 GB RAM.
- More capable than small 7B, 8B, or 14B models.
- Less risky than 70B-class models on a 16 GB VRAM GPU.

The model name should be defined in one obvious place so it can be changed later.

## Scope

Included:

- Add an `llm_client` module implementation for Ollama.
- Let `AmadeusChatModule` call the LLM client.
- Keep Core as the router and coordinator.
- Keep GUI calling only Core.
- Return clear error text if Ollama is unavailable or the model is missing.
- Update module docs and root README with Ollama setup steps.
- Verify imports, Core routing, and a direct Ollama client health check where possible.
- Commit and push the final project state to `origin/main` after implementation.

Excluded:

- Streaming responses.
- Conversation memory.
- Reasoning module integration.
- Skills integration.
- Mind map integration.
- Storage/database persistence.
- Model picker UI.
- Advanced settings UI.
- Cloud model providers.

## Components

### llm_client/ollama_client.py

Responsibilities:

- Define `OllamaClient`.
- Store default host and model settings.
- Send prompts to Ollama's local HTTP API.
- Return generated response text.
- Provide a small `health_check()` method.
- Convert connection/model failures into clear Python exceptions or readable error messages for the caller.

Must not:

- Own chat behavior.
- Store memory.
- Know about GUI widgets.
- Route requests between modules.

### llm_client/__init__.py

Responsibilities:

- Export `OllamaClient` and the default model name.

### amadeus_chat/chat_module.py

Responsibilities:

- Accept an LLM client dependency.
- Build a simple AMADEUS prompt from the user message.
- Ask the LLM client for a response.
- Return readable error text if the LLM client fails.

Must not:

- Import PyQt6.
- Talk directly to Core internals.
- Store conversation memory yet.

### amadeus_core/core.py

Responsibilities:

- Create the `OllamaClient`.
- Pass it into `AmadeusChatModule`.
- Continue routing user messages to Chat.

Must not:

- Generate LLM responses itself.
- Call Ollama directly from `handle_user_message()`.

### README and Module Docs

Responsibilities:

- Explain that Ollama is required for real local responses.
- Document setup:

```bash
ollama pull qwen3:32b
```

- Document run command:

```bash
py -3 main.py
```

## Data Flow

1. User sends message in GUI.
2. GUI calls `core.handle_user_message(message)`.
3. Core retrieves Chat from the registry.
4. Chat builds a simple prompt.
5. Chat calls `ollama_client.generate(prompt)`.
6. LLM Client calls Ollama local HTTP API.
7. Ollama returns generated text.
8. Chat returns that text to Core.
9. GUI displays the AMADEUS response.

## Error Handling

- If Ollama is not running, the Chat module should return a clear message telling the user to start Ollama.
- If `qwen3:32b` is not pulled, the Chat module should return a clear message telling the user to run `ollama pull qwen3:32b`.
- If Ollama returns malformed data, the LLM client should raise a readable error.
- The GUI should not crash because the LLM call failed.

## Testing And Verification

Verification steps:

1. Run Python compilation on current project packages.
2. Verify `OllamaClient` imports.
3. Verify Core can instantiate with the LLM client.
4. Verify Chat returns either a real model response or a clear Ollama setup error.
5. Verify GUI send behavior offscreen still calls Core and displays the returned response.
6. Check git status and diff.
7. Commit the full intended project state.
8. Push to `origin/main`.

## Git Handling

The repository is already initialized and connected to:

```text
https://github.com/dreamer441/MAIN-AMADEUS.git
```

After implementation and verification, create one commit containing the modular shell rebuild plus Ollama integration, then push it to `origin/main`.

Suggested commit message:

```text
feat: build modular amadeus shell with ollama
```
