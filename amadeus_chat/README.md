# AMADEUS Chat

The Chat module handles conversational messages.

It receives messages from Core and asks the LLM Client for a local Ollama response.

Chat should stay focused on conversation behavior. Core routes to Chat, and the GUI should not call Chat directly.
