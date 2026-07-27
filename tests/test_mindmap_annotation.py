"""Focused callable Mind Map retrieval tests without repository access."""

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

from amadeus_core import AmadeusCore
from amadeus_trace import TraceLogger
from annotation_module.annotation_parser import AnnotationParser
from annotation_module.callable_context_router import CallableContextRouter
from mindmap.models import GraphNode


class _FakeChat:
    """Captures the exact prompt and callable context sent to the LLM boundary."""

    def __init__(self) -> None:
        self.calls = []

    def handle_message(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return "LLM answer"


class _FakeMindMap:
    """Public Mind Map facade fake; deliberately has no repository attribute."""

    def __init__(self, search_result=None, recent_result=None, error=None) -> None:
        self.search_result = search_result or []
        self.recent_result = recent_result or []
        self.error = error
        self.search_calls = []
        self.recent_calls = []

    def search_nodes(self, query, limit=50):
        self.search_calls.append((query, limit))
        if self.error:
            raise self.error
        return self.search_result

    def list_recent_nodes(self, limit):
        self.recent_calls.append(limit)
        if self.error:
            raise self.error
        return self.recent_result

    def list_nodes(self):
        raise AssertionError("Callable retrieval must not materialize the full graph")


class MindMapCallableContextTests(unittest.TestCase):
    """Verify Mind Map annotations use only the injected public retrieval facade."""

    def _router(self, mind_map):
        self.chat = _FakeChat()
        self.persisted = []
        return CallableContextRouter(
            current_chat_id_provider=lambda: "chat-1",
            sheet_service=SimpleNamespace(),
            export_service=SimpleNamespace(),
            mind_map_module=mind_map,
            context_builder=SimpleNamespace(build_for_message=lambda *_args, **_kwargs: SimpleNamespace(
                recent_conversation=None,
                project_context=None,
                memory_context=None,
                chat_workspace_context=None,
                project_context_active=False,
            )),
            identity_prompt_builder=SimpleNamespace(build_for_chat=lambda **_kwargs: "identity"),
            chat_module_provider=lambda: self.chat,
            persist_exchange=lambda message, response: self.persisted.append((message, response)),
            build_response=lambda response, trace_logger, **_kwargs: {
                "response": response,
                "trace_events": trace_logger.get_trace_events(),
            },
        )

    @staticmethod
    def _node(node_id="1234", *, content="four digit node content", updated_at="2026-07-27T12:00:00"):
        return GraphNode(
            node_id=node_id,
            graph_id="main",
            node_type="note",
            title="Release work",
            description="Relevant implementation note",
            content=content,
            importance=0.8,
            confidence=0.9,
            status="active",
            metadata={"private": "must not be injected"},
            updated_at=updated_at,
        )

    def test_search_uses_public_api_and_sends_four_digit_node_content_to_llm(self) -> None:
        mind_map = _FakeMindMap(search_result=[self._node()])
        result = self._router(mind_map).handle_mindmap_prompt_request(
            AnnotationParser().parse("[mindmap][release] explain it"),  # type: ignore[arg-type]
            "[mindmap][release] explain it",
            TraceLogger(),
        )

        self.assertEqual([("release", 10)], mind_map.search_calls)
        self.assertEqual([], mind_map.recent_calls)
        self.assertEqual("explain it", self.chat.calls[0][0])
        context = self.chat.calls[0][1]["callable_context"]
        self.assertIn("Node ID: 1234", context)
        self.assertIn("Content: four digit node content", context)
        self.assertIn("retrieved from AMADEUS Mind Map", context)
        self.assertNotIn("must not be injected", context)
        self.assertEqual("LLM answer", result["response"])
        self.assertEqual(["Mind Map Query Started", "Mind Map Results Retrieved"], [
            event["title"] for event in result["trace_events"][:2]
        ])

    def test_empty_query_uses_bounded_public_recent_node_api(self) -> None:
        nodes = [self._node(str(index), updated_at=f"2026-07-{index:02d}T00:00:00") for index in range(1, 12)]
        mind_map = _FakeMindMap(recent_result=nodes[-10:])
        self._router(mind_map).handle_mindmap_prompt_request(
            AnnotationParser().parse("[mindmap]"),  # type: ignore[arg-type]
            "[mindmap]",
            TraceLogger(),
        )

        self.assertEqual([], mind_map.search_calls)
        self.assertEqual([10], mind_map.recent_calls)
        prompt, kwargs = self.chat.calls[0]
        self.assertEqual("Report the retrieved AMADEUS Mind Map context.", prompt)
        self.assertIn("Node ID: 11", kwargs["callable_context"])
        self.assertNotIn("Node ID: 1\n", kwargs["callable_context"])

    def test_no_matches_still_calls_llm_with_explicit_no_context(self) -> None:
        mind_map = _FakeMindMap()
        result = self._router(mind_map).handle_mindmap_prompt_request(
            AnnotationParser().parse("[mindmap][missing] what exists?"),  # type: ignore[arg-type]
            "[mindmap][missing] what exists?",
            TraceLogger(),
        )

        self.assertEqual("what exists?", self.chat.calls[0][0])
        self.assertIn("No matching Mind Map nodes", self.chat.calls[0][1]["callable_context"])
        self.assertIn("Mind Map No Matches", [event["title"] for event in result["trace_events"]])

    def test_query_failure_returns_safe_response_without_calling_llm(self) -> None:
        mind_map = _FakeMindMap(error=RuntimeError("private graph backend error"))
        result = self._router(mind_map).handle_mindmap_prompt_request(
            AnnotationParser().parse("[mindmap][private] explain"),  # type: ignore[arg-type]
            "[mindmap][private] explain",
            TraceLogger(),
        )

        self.assertEqual([], self.chat.calls)
        self.assertEqual("AMADEUS could not retrieve Mind Map context for that request. Please try again.", result["response"])
        self.assertIn("Mind Map Query Failed", [event["title"] for event in result["trace_events"]])
        self.assertNotIn("private graph backend error", str(result["trace_events"]))

    def test_core_route_finishes_after_safe_mindmap_events(self) -> None:
        mind_map = _FakeMindMap(search_result=[self._node(content="private node body")])
        client = type("Client", (), {"generate": lambda *_args, **_kwargs: "LLM answer"})()
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = AmadeusCore(llm_client=client, project_root=Path(temporary_directory))
            core.callable_context_router._mind_map_module = mind_map
            result = core.handle_user_message("[mindmap][release] explain it")

        titles = [event["title"] for event in result["trace_events"]]
        self.assertLess(titles.index("Mind Map Query Started"), titles.index("Mind Map Results Retrieved"))
        self.assertLess(titles.index("Mind Map Results Retrieved"), titles.index("Completed Exchange Stored"))
        self.assertEqual("Response Returned", titles[-1])
        self.assertEqual("completed", result["trace_events"][-1]["status"])
        self.assertNotIn("private node body", str(result["trace_events"]))

    def test_core_no_match_route_has_exact_safe_completed_lifecycle(self) -> None:
        mind_map = _FakeMindMap(search_result=[])
        client = type("Client", (), {"generate": lambda *_args, **_kwargs: "LLM answer"})()
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = AmadeusCore(llm_client=client, project_root=Path(temporary_directory))
            core.callable_context_router._mind_map_module = mind_map
            result = core.handle_user_message("[mindmap][missing] private question")

        events = result["trace_events"]
        self.assertEqual(
            [
                "Request Received",
                "Annotation Detected",
                "Mind Map Query Started",
                "Mind Map No Matches",
                "Mind Map Context Work Plan",
                "Context Building",
                "Chat Workspace Loaded",
                "Context Ready",
                "Preparing Answer Through Configured LLM",
                "Response Composed",
                "Completed Exchange Stored",
                "Output Ready",
                "Response Returned",
            ],
            [event["title"] for event in events],
        )
        self.assertEqual("completed", events[-1]["status"])
        self.assertNotIn("private question", str(events))

    def test_core_query_failure_has_exact_safe_failed_lifecycle(self) -> None:
        raw_error = "private graph backend failure"
        mind_map = _FakeMindMap(error=RuntimeError(raw_error))
        client = type("Client", (), {"generate": lambda *_args, **_kwargs: "LLM answer"})()
        with tempfile.TemporaryDirectory() as temporary_directory:
            core = AmadeusCore(llm_client=client, project_root=Path(temporary_directory))
            core.callable_context_router._mind_map_module = mind_map
            result = core.handle_user_message("[mindmap][private] private question")

        events = result["trace_events"]
        self.assertEqual(
            [
                "Request Received",
                "Annotation Detected",
                "Mind Map Query Started",
                "Mind Map Query Failed",
                "Completed Exchange Stored",
                "Output Ready",
                "Request Failed",
            ],
            [event["title"] for event in events],
        )
        self.assertEqual("failed", events[-1]["status"])
        self.assertEqual(
            "AMADEUS could not retrieve Mind Map context for that request. Please try again.",
            result["response"],
        )
        self.assertNotIn(raw_error, str(events))
        self.assertNotIn("private question", str(events))


if __name__ == "__main__":
    unittest.main()
