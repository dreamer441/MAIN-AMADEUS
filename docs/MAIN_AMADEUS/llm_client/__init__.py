"""AMADEUS LLM client package."""

from llm_client.ollama_client import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    OllamaClient,
    OllamaClientError,
)

__all__ = [
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
    "OllamaClient",
    "OllamaClientError",
]
