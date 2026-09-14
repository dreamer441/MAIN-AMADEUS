"""Focused Core tests for parser-owned annotation block orchestration."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amadeus_core.core import AmadeusCore
from amadeus_chat.chat_module import AmadeusChatModule
from amadeus_trace import TraceLogger
from annotation_module.callable_context_router import CallableContextRouter
from annotation_module.annotation_parser import AnnotationParser
from context_builder.chat_context_builder import ChatContextBuilder
from chat_workspace.conversation import ChatConversation
from llm_client import OllamaClientError
from response_modes import ResponseMode
from response_modes.response_payload import ResponsePresenter


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
            trace_logger.add_event("llm", "Preparing Answer Through Configured LLM", "Sending a prepared request to the configured LLM.")
            trace_logger.add_event("llm", "Response Composed", "Configured LLM returned a response for delivery.", level="success")
        return "chat response"


class _FakeExchanges:
    """Record owner-level persistence calls while preserving trace behavior."""

    def __init__(self, *, fail: bool = False) -> None:
        self.persisted: list[tuple[str, str]] = []
        self.fail = fail

    def persist_completed_exchange(self, message, response, trace_logger, response_decision=None):
        if self.fail:
            raise RuntimeError("private storage failure")
        self.persisted.append((message, response))
        trace_logger.add_event("module", "Completed Exchange Stored", "Stored the completed exchange in the active chat.", level="success")


def _conversation(*, chat=None, context_builder=None, exchanges=None, callable_context_router=None) -> ChatConversation:
    """Build the request owner directly with explicit, named collaborators."""
    history = SimpleNamespace(get_current_chat=lambda: SimpleNamespace(response_mode=ResponseMode.NORMAL))
    return ChatConversation(
        annotation_parser=AnnotationParser(),
        annotation_registry=_FakeRegistry(),
        annotation_context=object(),
        callable_context_router=callable_context_router or SimpleNamespace(),
        context_builder=context_builder or SimpleNamespace(build_for_message=lambda *_args, **_kwargs: SimpleNamespace(
            recent_conversation=None, project_context=None, memory_context=None,
            chat_workspace_context=None, project_context_active=False,
        )),
        identity_prompt_builder=SimpleNamespace(build_for_chat=lambda **_kwargs: "identity"),
        chat_module_provider=lambda: chat,
        advisor=SimpleNamespace(
            analyze_plain_message=lambda _message: SimpleNamespace(metadata_mode=None, suggested_write_actions=()),
            resolve_inferred_metadata=lambda _analysis: None,
            resolve_inferred_read_context=lambda _analysis: None,
            combine_callable_context=lambda first, second: first or second,
        ),
        creation_requests=SimpleNamespace(
            looks_like_creation_command=lambda _message: False,
            pending_action_from_inference=lambda *_args, **_kwargs: None,
        ),
        exchanges=exchanges or _FakeExchanges(),
        responses=ResponsePresenter(),
        metadata=SimpleNamespace(),
        chat_history_store=history,
        global_response_mode=ResponseMode.NORMAL,
    )


class ActiveChatLifecycleTests(unittest.TestCase):
    """Verify normal chat reports only genuine, safe lifecycle boundaries."""

    def _core(self) -> ChatConversation:
        chat = _FakeChat()
        chat_history = SimpleNamespace(
            get_current_chat_id=lambda: "chat-1",
            load_messages=lambda limit: [],
            get_chat=lambda _chat_id: None,
        )
        file_reader = SimpleNamespace(build_project_overview=lambda: "secret prompt")
        return _conversation(chat=chat, context_builder=ChatContextBuilder(chat_history, file_reader))

    def test_normal_chat_emits_safe_lifecycle_events(self) -> None:
        result = self._core().handle_user_message("Explain the project")

        titles = [event["title"] for event in result["trace_events"]]
        self.assertEqual(
            [
                "Request Received",
                "Request Route",
                "Normal Chat Work Plan",
                "Context Building",
                "Project Overview Selected",
                "Context Ready",
                "Response Mode Resolved",
                "Preparing Answer Through Configured LLM",
                "Response Composed",
                "Completed Exchange Stored",
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
        core.chat_module_provider = lambda: AmadeusChatModule(failing_client)

        result = core.handle_user_message("hello")

        events = result["trace_events"]
        self.assertEqual(
            ["Request Received", "Request Route", "Normal Chat Work Plan", "Context Building", "Context Ready", "Response Mode Resolved", "Preparing Answer Through Configured LLM", "Configured LLM Unavailable", "Completed Exchange Stored", "Request Failed"],
            [event["title"] for event in events],
        )
        self.assertEqual(
            ["running", "running", "running", "running", "completed", "running", "running", "failed", "completed", "failed"],
            [event["status"] for event in events],
        )
        self.assertEqual("AMADEUS LLM error: sensitive backend failure", result["response"])
        self.assertNotIn(error_text, str(events))

    def test_missing_chat_emits_terminal_failed_lifecycle(self) -> None:
        core = self._core()
        core.chat_module_provider = lambda: None

        result = core.handle_user_message("hello")

        events = result["trace_events"]
        self.assertEqual(["Request Received", "Request Route", "Normal Chat Work Plan", "Request Failed"], [event["title"] for event in events])
        self.assertEqual(["running", "running", "running", "failed"], [event["status"] for event in events])
        self.assertEqual("AMADEUS error: chat module is not registered.", result["response"])

    def test_side_ask_declares_no_persist_plan_without_exposing_question(self) -> None:
        with tempfile.TemporaryDirectory() as project_root:
            client = type("Client", (), {"generate": lambda *_args, **_kwargs: "side answer"})()
            result = AmadeusCore(llm_client=client, project_root=Path(project_root)).handle_side_ask("private Side Ask question")

        events = result["trace_events"]
        titles = [event["title"] for event in events]
        self.assertIn("Side Ask Work Plan", titles)
        self.assertNotIn("Completed Exchange Stored", titles)
        self.assertEqual("completed", events[-1]["status"])
        self.assertNotIn("private Side Ask question", str(events))


class AnnotationBlockCoreTests(unittest.TestCase):
    """Verify Core consumes parser output without interpreting block delimiters."""

    def _core(self) -> tuple[ChatConversation, _FakeChat, list[tuple[str, str]]]:
        chat = _FakeChat()
        exchanges = _FakeExchanges()
        core = _conversation(chat=chat, exchanges=exchanges, context_builder=SimpleNamespace(build_for_message=lambda prompt, **_kwargs: SimpleNamespace(
            recent_conversation="history",
            project_context=None,
            memory_context=None,
            chat_workspace_context=None,
            project_context_active=False,
        )))
        return core, chat, exchanges.persisted

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

    def test_block_only_save_event_precedes_successful_terminal_event(self) -> None:
        core, _chat, _persisted = self._core()
        core.annotation_parser = AnnotationParser()
        result = core.handle_user_message("[identity][end]")

        self.assertEqual(
            ["Request Received", "Annotation Block Detected", "Annotation Block Work Plan", "Completed Exchange Stored", "Output Ready", "Response Returned"],
            [event["title"] for event in result["trace_events"]],
        )
        self.assertEqual("completed", result["trace_events"][-1]["status"])

    def test_block_only_save_failure_has_no_storage_event_and_fails_terminally(self) -> None:
        core, _chat, _persisted = self._core()
        core.annotation_parser = AnnotationParser()
        core.exchanges = _FakeExchanges(fail=True)

        result = core.handle_user_message("[identity][end]")

        titles = [event["title"] for event in result["trace_events"]]
        self.assertNotIn("Completed Exchange Stored", titles)
        self.assertEqual("failed", result["trace_events"][-1]["status"])
        self.assertNotIn("private storage failure", str(result["trace_events"]))
        self.assertNotIn("private storage failure", result["response"])


class CallableContextMonitorTests(unittest.TestCase):
    """Verify callable sheet/export routes report only completed persistence."""

    def _core(self, *, fail_save: bool = False) -> ChatConversation:
        context_bundle = SimpleNamespace(
            recent_conversation=None,
            project_context=None,
            memory_context=None,
            chat_workspace_context=None,
            project_context_active=False,
        )
        sheet = SimpleNamespace(title="Quarterly plan", scope="chat", sheet_id="sheet-1")
        selection = SimpleNamespace(record=SimpleNamespace(chat_title="Private Archived Chat"), range_label="1-2")
        core = _conversation(chat=_FakeChat(), exchanges=_FakeExchanges(fail=fail_save))
        core.callable_context_router = CallableContextRouter(
            current_chat_id_provider=lambda: "chat-1",
            sheet_service=SimpleNamespace(
                resolve_target=lambda *_args, **_kwargs: (sheet, None, "chat"),
                build_prompt_context=lambda _sheet: "sheet context",
                build_panel_payload=lambda **_kwargs: {"type": "sheets"},
            ),
            export_service=SimpleNamespace(
                parse_annotation_target=lambda _args: (SimpleNamespace(mode="use", title_or_id="archive", range_token="1-2"), None),
                resolve_selection=lambda *_args: (selection, None),
                build_prompt_context=lambda _selection: "export context",
                build_materials_panel_payload=lambda *_args: {"type": "materials"},
            ),
            mind_map_module=SimpleNamespace(search_nodes=lambda *_args, **_kwargs: [], list_nodes=lambda: []),
            context_builder=SimpleNamespace(build_for_message=lambda *_args, **_kwargs: context_bundle),
            identity_prompt_builder=SimpleNamespace(build_for_chat=lambda **_kwargs: "identity"),
            chat_module_provider=lambda: _FakeChat(),
            persist_exchange=(lambda _message, _response, _decision=None: (_ for _ in ()).throw(RuntimeError("private storage failure"))) if fail_save else (lambda _message, _response, _decision=None: None),
            build_response=core.responses.build_response_payload,
        )
        return core

    def test_callable_sheet_and_export_save_before_successful_terminal_event(self) -> None:
        for message, plan_title in (
            ("[sheet][chat][Quarterly plan] private sheet question", "Sheet Context Work Plan"),
            ("[export][use][Archived chat][1-2] private export question", "Export Context Work Plan"),
        ):
            with self.subTest(message=message):
                result = self._core().handle_user_message(message)
                titles = [event["title"] for event in result["trace_events"]]
                self.assertNotIn("Annotation Work Plan", titles)
                self.assertLess(titles.index(plan_title), titles.index("Completed Exchange Stored"))
                self.assertLess(titles.index("Completed Exchange Stored"), titles.index("Output Ready"))
                self.assertEqual("completed", result["trace_events"][-1]["status"])
                self.assertNotIn("private", str(result["trace_events"]))

    def test_callable_sheet_and_export_save_failure_has_no_storage_event_and_fails_terminally(self) -> None:
        for message in (
            "[sheet][chat][Quarterly plan] private sheet question",
            "[export][use][Archived chat][1-2] private export question",
        ):
            with self.subTest(message=message):
                result = self._core(fail_save=True).handle_user_message(message)
                titles = [event["title"] for event in result["trace_events"]]
                self.assertNotIn("Completed Exchange Stored", titles)
                self.assertEqual("failed", result["trace_events"][-1]["status"])
                self.assertNotIn("private", str(result["trace_events"]))
                self.assertNotIn("private", result["response"])

    def test_callable_resolution_events_do_not_expose_titles_or_resolver_errors(self) -> None:
        core = self._core()
        raw_error = "raw resolver error for Private Lookup Target"
        core.callable_context_router._export_service.resolve_selection = lambda *_args: (None, raw_error)

        result = core.handle_user_message("[export][use][Private Lookup Target] private prompt")

        trace = str(result["trace_events"])
        self.assertIn("Could not resolve the requested export context.", trace)
        self.assertNotIn("Private Lookup Target", trace)
        self.assertNotIn(raw_error, trace)
        self.assertNotIn("private prompt", trace)

        core = self._core()
        core.callable_context_router._sheet_service.resolve_target = lambda *_args, **_kwargs: (None, raw_error, "chat")

        result = core.handle_user_message("[sheet][chat][Private Lookup Target] private prompt")

        trace = str(result["trace_events"])
        self.assertIn("Could not resolve the requested sheet.", trace)
        self.assertNotIn("Private Lookup Target", trace)
        self.assertNotIn(raw_error, trace)
        self.assertNotIn("private prompt", trace)


class ExportPersistenceMonitorTests(unittest.TestCase):
    """Verify Process Monitor reports only exports that were actually saved."""

    @staticmethod
    def _core(project_root: Path) -> AmadeusCore:
        return AmadeusCore(
            llm_client=type("Client", (), {"generate": lambda *_args, **_kwargs: "answer"})(),
            project_root=project_root,
        )

    def test_direct_export_emits_safe_saved_event_after_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = self._core(Path(temporary_directory))
            core.create_chat("Private Direct Export")
            core.chat_history_store.append_message("User", "private export body")

            result = core.handle_user_message("[export]")

        events = result["trace_events"]
        saved_event = next(event for event in events if event["title"] == "Export Saved")
        self.assertEqual("Export files were saved for the requested context.", saved_event["summary"])
        self.assertEqual("completed", saved_event["status"])
        self.assertEqual("completed", events[-1]["status"])
        self.assertNotIn("Private Direct Export", str(events))
        self.assertNotIn("private export body", str(events))

    def test_direct_export_failure_has_no_saved_event_and_fails_terminally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = self._core(Path(temporary_directory))
            core.export_service.export_chat = lambda *_args: (_ for _ in ()).throw(RuntimeError("private export failure"))

            result = core.handle_user_message("[export]")

        self.assertNotIn("Export Saved", [event["title"] for event in result["trace_events"]])
        self.assertEqual("failed", result["trace_events"][-1]["status"])
        self.assertNotIn("private export failure", str(result["trace_events"]))

    def test_callable_export_emits_safe_saved_event_after_on_demand_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = self._core(Path(temporary_directory))
            core.create_chat("Private Callable Export")
            core.chat_history_store.append_message("User", "private exported body")

            result = core.handle_user_message("[export][use][Private Callable Export][1-2] private prompt")

        events = result["trace_events"]
        self.assertIn("Export Saved", [event["title"] for event in events])
        self.assertEqual("completed", events[-1]["status"])
        self.assertNotIn("Private Callable Export", str(events))
        self.assertNotIn("private exported body", str(events))
        self.assertNotIn("private prompt", str(events))

    def test_callable_export_failure_has_no_saved_event_and_fails_terminally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = self._core(Path(temporary_directory))
            core.create_chat("Private Callable Export")
            core.export_service.export_chat = lambda *_args: (_ for _ in ()).throw(RuntimeError("private export failure"))

            result = core.handle_user_message("[export][use][Private Callable Export] private prompt")

        self.assertNotIn("Export Saved", [event["title"] for event in result["trace_events"]])
        self.assertEqual("failed", result["trace_events"][-1]["status"])
        self.assertNotIn("private export failure", str(result["trace_events"]))


if __name__ == "__main__":
    unittest.main()
