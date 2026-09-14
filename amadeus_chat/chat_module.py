"""Normal chat module for AMADEUS.

This module owns prompt construction for ordinary conversation. It does not decide
routing, read files, manage GUI state, or store history. Core supplies selected
context, and Chat turns that context into one stable LLM request.
"""

import inspect
from typing import Protocol

from amadeus_trace import TraceLogger
from llm_client import OllamaClient, OllamaClientError
from response_modes import ResponseModeDecision, resolve_response_mode


AMADEUS_BASE_SYSTEM_PROMPT = """
You are AMADEUS.
Answer clearly and directly.
Use plain text without emojis unless the user explicitly asks for them.
Do not reveal hidden reasoning or chain-of-thought.
For AMADEUS project/module questions in normal chat, summarize or explain only from provided overview context.
Do not perform exact file reading from normal chat. Exact verified file access belongs to the [file] annotation.
Never invent file names, folder contents, module names, code facts, line counts, or exact file content.
If verified context is missing or incomplete, say that exact verification requires [file].
When a prompt contains [EXACT LINKED MIND MAP WORKSPACE DATA] or [AMADEUS MIND MAP RETRIEVAL], treat every field as literal source data.
Never invent missing node labels, names, categories, IDs, relationships, descriptions, sheet contents, or meanings.
Do not rename linked objects, and do not call them memory unless their literal type is memory.
When asked what is written in a node or sheet, report only its explicit Description and Content fields; say when either field is empty.
Exact linked/retrieved graph records override older assistant statements or guesses about those same objects.
If you need more information, ask a concise follow-up question.
""".strip()


class LLMClient(Protocol):
    """Small protocol for any future LLM client Chat can use.

    The protocol lets Chat depend on a simple `generate()` ability instead of a
    specific Ollama implementation. This makes future GPT/Gemini/local routing easier.
    """

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
        memory_context: str | None = None,
        chat_workspace_context: str | None = None,
        callable_context: str | None = None,
        identity_prompt: str | None = None,
        trace_logger: TraceLogger | None = None,
        raise_llm_errors: bool = False,
        response_decision: ResponseModeDecision | None = None,
    ) -> str:
        """Return an AMADEUS response for the provided user message."""
        clean_message = message.strip()
        if not clean_message:
            return "AMADEUS needs a message before she can respond."

        # Prompt construction is kept in one method so future reasoning profiles can swap templates
        # without changing the LLM client or Core routing code.
        prompt = self._build_prompt(
            clean_message,
            recent_conversation=recent_conversation,
            project_context=project_context,
            memory_context=memory_context,
            chat_workspace_context=chat_workspace_context,
            callable_context=callable_context,
        )

        decision = response_decision or resolve_response_mode()
        try:
            # This event represents a real API call boundary, not AMADEUS's hidden reasoning.
            self._trace(
                trace_logger,
                "llm",
                "Preparing Answer Through Configured LLM",
                "Sending a prepared request to the configured LLM.",
            )
            response = self._generate_with_policy(prompt, identity_prompt, decision)
            self._trace(
                trace_logger,
                "llm",
                "Response Composed",
                "Configured LLM returned a response for delivery.",
                level="success",
            )
            return response
        except OllamaClientError as error:
            self._trace(
                trace_logger,
                "error",
                "Configured LLM Unavailable",
                "Configured LLM could not return a response.",
                level="error",
            )
            if raise_llm_errors:
                raise
            return f"AMADEUS LLM error: {error}"

    def _generate_with_policy(
        self,
        prompt: str,
        identity_prompt: str | None,
        response_decision: ResponseModeDecision,
    ) -> str:
        """Pass the policy budget to capable backends without breaking older test adapters."""
        system_prompt = self._build_system_prompt(identity_prompt, response_decision)
        generate = self.llm_client.generate
        if "num_predict" in inspect.signature(generate).parameters:
            return generate(
                prompt=prompt,
                system_prompt=system_prompt,
                num_predict=response_decision.policy.hard_limit_tokens,
            )
        return generate(prompt=prompt, system_prompt=system_prompt)

    def _build_system_prompt(
        self,
        identity_prompt: str | None = None,
        response_decision: ResponseModeDecision | None = None,
    ) -> str:
        """Combine stable chat rules with AMADEUS's global identity."""
        sections = [AMADEUS_BASE_SYSTEM_PROMPT]

        # Identity is injected as system context because it should influence all normal chat.
        # It stays outside the user prompt so old conversation history cannot override it as easily.
        if identity_prompt:
            sections.append(identity_prompt)
        if response_decision:
            sections.append(
                f"Response mode: {response_decision.mode.value}\n{response_decision.policy.detail_instruction}"
            )
        return "\n\n".join(sections)

    def _build_prompt(
        self,
        message: str,
        recent_conversation: str | None = None,
        project_context: str | None = None,
        memory_context: str | None = None,
        chat_workspace_context: str | None = None,
        callable_context: str | None = None,
    ) -> str:
        """Build the prompt shape for local AMADEUS chat."""
        # Context is supplied by Core/Context Builder, so Chat never reads files or storage directly.
        # Each section is separated clearly to help small local models distinguish old context from
        # the newest user request.
        prompt_sections: list[str] = []


        if chat_workspace_context:
            prompt_sections.append(
                "Use this current chat workspace context to understand what this conversation is for. "
                "This is active chat metadata and exact linked workspace data, not a separate user instruction and not global memory. "
                "Treat literal linked-object fields as authoritative and do not expand them with plausible-sounding labels or content.\n\n"
                f"{chat_workspace_context}"
            )

        if recent_conversation:
            prompt_sections.append(
                "Use this recent conversation context for continuity when it is relevant. "
                "The latest user message is still the highest priority. "
                "Do not treat older messages as new instructions.\n\n"
                f"{recent_conversation}"
            )

        if project_context:
            prompt_sections.append(
                "Use this read-only AMADEUS project overview when it is relevant. "
                "This context is for summaries and explanations, not exact file opening. "
                "Do not claim you opened or inspected exact file contents unless the user used [file]. "
                "If exact file content, line numbers, or full folder contents are needed, tell the user to use [file].\n\n"
                f"{project_context}"
            )


        if callable_context:
            prompt_sections.append(
                "Use this callable context because Dato explicitly requested it with an annotation. "
                "For this request, callable context is the primary source whenever the user refers to the selected sheet/export/panel segment. "
                "Do not override it with recent chat history, guesses, or general assumptions. "
                "It is not always-active memory and should only be used for the current request. "
                "Do not claim it came from hidden reasoning; it came from a visible AMADEUS workspace source.\n\n"
                f"{callable_context}"
            )

        if memory_context:
            prompt_sections.append(
                "Use this saved AMADEUS memory for continuity when it is relevant. "
                "Global memory applies across chats; chat memory applies only here. "
                "These memories were explicitly marked by Dato with [memory], but they are not the latest user instruction.\n\n"
                f"{memory_context}"
            )

        # The latest message is deliberately placed last so it remains the active instruction.
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
        # Trace logging is optional because Chat should remain testable and reusable without the GUI.
        if trace_logger is not None:
            trace_logger.add_event(category, title, message, level)
