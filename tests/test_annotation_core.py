"""Focused Core tests for parser-owned annotation block orchestration."""

import unittest
from types import SimpleNamespace

from amadeus_core.core import AmadeusCore
from amadeus_chat.chat_module import AmadeusChatModule
from amadeus_trace import TraceLogger
from annotation_module.annotation_parser import AnnotationParser
from context_builder.chat_context_builder import ChatContextBuilder
from llm_client import OllamaClientError


class _FakeRegistry:
    def handle(self, annotation, context):
        return f"resolved {annotation.annotation_name}"


class _FakeChat:
    def __init__(self) -> None:
        self.calls = []

    def handle_message(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        trace_logger = kwargs.get("trace_logger")
        if trace_logger is not None:
            trace_logger.add_event("llm", "LLM Request", "Sending request to the configured LLM.")
            trace_logger.add_event("llm", "LLM Response", "Configured LLM returned a response.", level="success")
        return "chat response"


class ActiveChatLifecycleTests(unittest.TestCase):
    """Verify normal chat reports only genuine, safe lifecycle boundaries."""

    def _core(self) -> AmadeusCore:
        core = object.__new__(AmadeusCore)
        core.annotation_parser = AnnotationParser()
        core.module_registry = SimpleNamespace(get=lambda name: _FakeChat() if name == "chat" else None)
        chat_history = SimpleNamespace(
            get_current_chat_id=lambda: "chat-1",
            load_messages=lambda limit: [],
            get_chat=lambda _chat_id: None,
        )
        file_reader = SimpleNamespace(build_project_overview=lambda: "secret prompt")
        core.context_builder = ChatContextBuilder(chat_history, file_reader)
        core.identity_prompt_builder = SimpleNamespace(build_for_chat=lambda **_kwargs: "identity")
        core._persist_exchange = lambda _message, _response: None
        return core

    def test_normal_chat_emits_safe_lifecycle_events(self) -> None:
        result = self._core().handle_user_message("Explain the project")

        titles = [event["title"] for event in result["trace_events"]]
        self.assertEqual(
            [
                "Request Received",
                "Request Route",
                "Context Building",
                "Context Ready",
                "LLM Request",
                "LLM Response",
                "Response Returned",
            ],
            titles,
        )
        self.assertNotIn("secret prompt", str(result["trace_events"]))
        self.assertEqual(1, len({event["run_id"] for event in result["trace_events"]}))

    def test_context_failure_emits_failed_run_event(self) -> None:
        core = self._core()
        core.context_builder.build_for_message = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("context unavailable"))

        result = core.handle_user_message("hello")

        self.assertEqual("failed", result["trace_events"][-1]["status"])

    def test_llm_failure_emits_safe_failed_lifecycle_and_preserves_response(self) -> None:
        core = self._core()
        error_text = "sensitive backend failure"
        failing_client = type(
            "Client",
            (),
            {"generate": lambda *_args, **_kwargs: (_ for _ in ()).throw(OllamaClientError(error_text))},
        )()
        core.module_registry = SimpleNamespace(get=lambda name: AmadeusChatModule(failing_client) if name == "chat" else None)

        result = core.handle_user_message("hello")

        events = result["trace_events"]
        self.assertEqual(
            ["Request Received", "Request Route", "Context Building", "Context Ready", "LLM Request", "LLM Response", "Request Failed"],
            [event["title"] for event in events],
        )
        self.assertEqual(["running", "running", "running", "completed", "running", "failed", "failed"], [event["status"] for event in events])
        self.assertEqual("AMADEUS LLM error: sensitive backend failure", result["response"])
        self.assertNotIn(error_text, str(events))

    def test_missing_chat_emits_terminal_failed_lifecycle(self) -> None:
        core = self._core()
        core.module_registry = SimpleNamespace(get=lambda _name: None)

        result = core.handle_user_message("hello")

        events = result["trace_events"]
        self.assertEqual(["Request Received", "Request Route", "Request Failed"], [event["title"] for event in events])
        self.assertEqual(["running", "running", "failed"], [event["status"] for event in events])
        self.assertEqual("AMADEUS error: chat module is not registered.", result["response"])


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
