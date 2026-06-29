# AMADEUS First Steps

This first version creates a working AMADEUS shell.

## Created Now

- Core module registry.
- Core message routing.
- Chat module connected to the LLM Client.
- Ollama LLM Client using `qwen3:32b`.
- PyQt6 GUI window.
- Placeholder folders for future modules.
- Documentation for every module folder.

## What Works Now

You can open the AMADEUS window, type a message, press Send or Enter, and see an AMADEUS response from local Ollama when Ollama is running and `qwen3:32b` is installed.

If Ollama is missing or the model has not been pulled yet, AMADEUS returns a readable setup error instead of crashing.

## What Should Come Next

The next step should be a formal module interface contract so future modules can register capabilities, expose commands, report status, and request permission-protected actions.
