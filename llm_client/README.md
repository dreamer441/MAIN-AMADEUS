# LLM Client

The LLM Client connects AMADEUS to local Ollama models through one clean module boundary.

The default lightweight model is:

```text
llama3.2:latest
```

Install Ollama and pull the model before running AMADEUS:

```bash
ollama pull llama3.2
```

The heavier `qwen3:32b` model can stay installed for later heavier tasks.

Other modules should not call Ollama directly. They should use the LLM Client boundary so model integration stays replaceable.
