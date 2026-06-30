from typing import Protocol

from llm_client import OllamaClient, OllamaClientError


AMADEUS_BASE_SYSTEM_PROMPT = """
You are AMADEUS.
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

    def handle_message(
        self,
        message: str,
        context: str | None = None,
        identity_prompt: str | None = None,
    ) -> str:
        """Return an AMADEUS response for the provided user message."""
        clean_message = message.strip()
        if not clean_message:
            return "AMADEUS needs a message before she can respond."

        prompt = self._build_prompt(clean_message, context=context)

        try:
            return self.llm_client.generate(
                prompt=prompt,
                system_prompt=self._build_system_prompt(identity_prompt),
            )
        except OllamaClientError as error:
            return f"AMADEUS LLM error: {error}"

    def _build_system_prompt(self, identity_prompt: str | None = None) -> str:
        """Combine stable chat rules with AMADEUS's global identity."""
        if not identity_prompt:
            return AMADEUS_BASE_SYSTEM_PROMPT

        return f"{AMADEUS_BASE_SYSTEM_PROMPT}\n\n{identity_prompt}"

    def _build_prompt(self, message: str, context: str | None = None) -> str:
        """Build the first simple prompt shape for local AMADEUS chat."""
        # Context is supplied by Core, so Chat can use project knowledge without reading files itself.
        if context:
            return (
                "Use this read-only AMADEUS project context when it is relevant. "
                "Do not claim you inspected files beyond this context.\n\n"
                f"{context}\n\n"
                f"User message:\n{message}\n\n"
                "Respond as AMADEUS."
            )

        return f"User message:\n{message}\n\nRespond as AMADEUS."
