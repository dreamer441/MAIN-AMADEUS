# AMADEUS

AMADEUS is a local-first personal AI project designed to grow as a clean modular desktop system.

This first rebuild is intentionally small. It creates a working shell with:

- AMADEUS Core
- AMADEUS Chat module
- AMADEUS PyQt6 GUI
- Ollama local LLM client
- Placeholder folders for future modules

## Current Behavior

The app opens a desktop window. You can type a message, press Send or Enter, and AMADEUS routes it through Core to the Chat module.

Chat now uses the local Ollama LLM client. The default model is `qwen3:32b`.

## How To Run

Install Ollama from:

```text
https://ollama.com
```

Pull the default AMADEUS model:

```bash
ollama pull qwen3:32b
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

If Windows does not recognize `python`, try:

```bash
py -3 main.py
```

## Current Scope

This version includes a simple local Ollama LLM connection. It does not include real reasoning, memory, skills, mind map, storage, advanced permissions, streaming responses, or model picker UI yet.
