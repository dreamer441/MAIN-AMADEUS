from typing import Protocol

from amadeus_trace import TraceLogger
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
        recent_conversation: str | None = None,
        project_context: str | None = None,
        identity_prompt: str | None = None,
        trace_logger: TraceLogger | None = None,
    ) -> str:
        """Return an AMADEUS response for the provided user message."""
        clean_message = message.strip()
        if not clean_message:
            return "AMADEUS needs a message before she can respond."

        self._trace(
            trace_logger,
            "module",
            "Chat Module",
            "Chat module is building the prompt for the LLM client.",
        )
        prompt = self._build_prompt(
            clean_message,
            recent_conversation=recent_conversation,
            project_context=project_context,
        )

        try:
            # This event represents a real API call boundary, not AMADEUS's hidden reasoning.
            self._trace(
                trace_logger,
                "llm",
                "LLM Client",
                "Sending message to the configured Ollama model.",
            )
            response = self.llm_client.generate(
                prompt=prompt,
                system_prompt=self._build_system_prompt(identity_prompt),
            )
            self._trace(
                trace_logger,
                "llm",
                "LLM Client",
                "Ollama returned a response successfully.",
                level="success",
            )
            return response
        except OllamaClientError as error:
            self._trace(
                trace_logger,
                "error",
                "LLM Client Error",
                f"Ollama client error: {error}",
                level="error",
            )
            return f"AMADEUS LLM error: {error}"

    def _build_system_prompt(self, identity_prompt: str | None = None) -> str:
        """Combine stable chat rules with AMADEUS's global identity."""
        if not identity_prompt:
            return AMADEUS_BASE_SYSTEM_PROMPT

        return f"{AMADEUS_BASE_SYSTEM_PROMPT}\n\n{identity_prompt}"

    def _build_prompt(
        self,
        message: str,
        recent_conversation: str | None = None,
        project_context: str | None = None,
    ) -> str:
        """Build the prompt shape for local AMADEUS chat."""
        # Context is supplied by Core/Context Builder, so Chat never reads files or storage directly.
        prompt_sections: list[str] = []

        if recent_conversation:
            prompt_sections.append(
                "Use this recent conversation context for continuity when it is relevant. "
                "The latest user message is still the highest priority. "
                "Do not treat older messages as new instructions.\n\n"
                f"{recent_conversation}"
            )

        if project_context:
            prompt_sections.append(
                "Use this read-only AMADEUS project context when it is relevant. "
                "Do not claim you inspected files beyond this context.\n\n"
                f"{project_context}"
            )

        prompt_sections.append(f"User message:\n{message}\n\nRespond as AMADEUS.")
        return "\n\n---\n\n".join(prompt_sections)

    def _trace(
        self,
        trace_logger: TraceLogger | None,
        category: str,
        title: str,
        message: str,
        level: str = "info",
    ) -> None:
        """Record a trace event only when Core provided a logger."""
        if trace_logger is not None:
            trace_logger.add_event(category, title, message, level)
