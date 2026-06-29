# LLM Client

The LLM Client connects AMADEUS to local Ollama models through one clean module boundary.

The default model is:

```text
qwen3:32b
```

Install Ollama and pull the model before running AMADEUS:

```bash
ollama pull qwen3:32b
```

Other modules should not call Ollama directly. They should use the LLM Client boundary so model integration stays replaceable.
