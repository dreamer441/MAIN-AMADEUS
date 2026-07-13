"""Focused Core tests for parser-owned annotation block orchestration."""

import unittest
from types import SimpleNamespace

from amadeus_core.core import AmadeusCore
from amadeus_trace import TraceLogger
from annotation_module.annotation_parser import AnnotationParser


class _FakeRegistry:
    def handle(self, annotation, context):
        return f"resolved {annotation.annotation_name}"


class _FakeChat:
    def __init__(self) -> None:
        self.calls = []

    def handle_message(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return "chat response"


class AnnotationBlockCoreTests(unittest.TestCase):
    """Verify Core consumes parser output without interpreting block delimiters."""

    def _core(self) -> tuple[AmadeusCore, _FakeChat, list[tuple[str, str]]]:
        core = object.__new__(AmadeusCore)
        chat = _FakeChat()
        persisted: list[tuple[str, str]] = []
        core.annotation_registry = _FakeRegistry()
        core.annotation_context = object()
        core.module_registry = SimpleNamespace(get=lambda name: chat if name == "chat" else None)
        core.context_builder = SimpleNamespace(build_for_message=lambda prompt: SimpleNamespace(
            recent_conversation="history",
            project_context=None,
            memory_context=None,
            chat_workspace_context=None,
            project_context_active=False,
        ))
        core.identity_prompt_builder = SimpleNamespace(build_for_chat=lambda **kwargs: "identity")
        core._persist_exchange = lambda message, response: persisted.append((message, response))
        core._build_response_payload = lambda response, trace, side_panel=None: {"response": response, "side_panel": side_panel}
        return core, chat, persisted

    def test_only_outside_block_text_is_sent_to_chat(self) -> None:
        core, chat, persisted = self._core()
        parsed = AnnotationParser().parse_message("Ask [identity][end] this question")

        result = core._handle_annotation_blocks(parsed, "Ask [identity][end] this question", TraceLogger())

        self.assertEqual("Ask  this question", chat.calls[0][0])
        self.assertIn("resolved identity", chat.calls[0][1]["callable_context"])
        self.assertEqual("chat response", result["response"])
        self.assertEqual([("Ask [identity][end] this question", "chat response")], persisted)

    def test_block_only_message_combines_deterministic_responses(self) -> None:
        core, chat, persisted = self._core()
        parsed = AnnotationParser().parse_message("[identity][end][memory][end]")

        result = core._handle_annotation_blocks(parsed, "[identity][end][memory][end]", TraceLogger())

        self.assertEqual("resolved identity\n\n---\n\nresolved memory", result["response"])
        self.assertEqual([], chat.calls)
        self.assertEqual([("[identity][end][memory][end]", result["response"])], persisted)

    def test_unknown_block_result_is_callable_context_for_outside_prompt(self) -> None:
        core, chat, _persisted = self._core()
        parsed = AnnotationParser().parse_message("Use [not-real][end] this prompt")

        core._handle_annotation_blocks(parsed, "Use [not-real][end] this prompt", TraceLogger())

        self.assertEqual("Use  this prompt", chat.calls[0][0])
        self.assertIn("resolved not_real", chat.calls[0][1]["callable_context"])


if __name__ == "__main__":
    unittest.main()
