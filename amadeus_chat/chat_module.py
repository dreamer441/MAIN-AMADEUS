from typing import Protocol

from llm_client import OllamaClient, OllamaClientError


AMADEUS_SYSTEM_PROMPT = """
You are AMADEUS, a local-first personal AI assistant.
Answer clearly and directly.
Use plain text without emojis unless the user explicitly asks for them.
Do not reveal hidden reasoning or chain-of-thought.
If you need more information, ask a concise follow-up question.
""".strip()


class LLMClient(Protocol):
    """Small protocol for any future LLM client Chat can use."""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate a response for a prompt."""


class AmadeusChatModule:
    """First simple chat module for the AMADEUS shell."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        # Chat depends on an LLM boundary, not directly on Core or GUI.
        self.llm_client = llm_client or OllamaClient()

    def handle_message(self, message: str) -> str:
        """Return an AMADEUS response for the provided user message."""
        clean_message = message.strip()
        if not clean_message:
            return "AMADEUS needs a message before she can respond."

        prompt = self._build_prompt(clean_message)

        try:
            return self.llm_client.generate(
                prompt=prompt,
                system_prompt=AMADEUS_SYSTEM_PROMPT,
            )
        except OllamaClientError as error:
            return f"AMADEUS LLM error: {error}"

    def _build_prompt(self, message: str) -> str:
        """Build the first simple prompt shape for local AMADEUS chat."""
        # Reasoning and memory will connect here later. For now, Chat sends only the user text.
        return f"User message:\n{message}\n\nRespond as AMADEUS."
