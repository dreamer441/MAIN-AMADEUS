# AMADEUS First Steps

This first version creates a working AMADEUS shell.

## Created Now

- Core module registry.
- Core message routing.
- Chat module connected to the LLM Client.
- Ollama LLM Client using `llama3.2:latest` by default.
- Read-only `[file]` annotation support.
- PyQt6 GUI window.
- Placeholder folders for future modules.
- Documentation for every module folder.

## What Works Now

You can open the AMADEUS window, type a message, press Send or Enter, and see an AMADEUS response from local Ollama when Ollama is running and `llama3.2:latest` is installed.

If Ollama is missing or the model has not been pulled yet, AMADEUS returns a readable setup error instead of crashing.

You can also send `[file]` to list readable project module folders, or `[file][amadeus_core]` to read a module's documentation.

## What Should Come Next

The next step should be a formal module interface contract so future modules can register capabilities, expose commands, report status, and request permission-protected actions.
