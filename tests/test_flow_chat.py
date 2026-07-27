"""Focused persistence and metadata-isolation tests for Flow Chat."""

import json
import multiprocessing
import tempfile
import threading
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

from chat_registry import ChatRegistry
from flow_chat import FlowChatMessage, FlowChatStore, FlowContextBuilder
from amadeus_core.core import AmadeusCore
from amadeus_trace import TraceLogger
from llm_client import OllamaClientError
from storage import ChatHistoryStore


def _append_message_in_process(
    root: str,
    message: str,
    append_started,
    write_started,
    allow_write,
) -> None:
    """Append a message while allowing the parent test to hold its file replacement."""
    store = FlowChatStore(Path(root))
    original_atomic_write = store._atomic_write

    def controlled_atomic_write(content: str) -> None:
        write_started.set()
        allow_write.wait(timeout=5)
        original_atomic_write(content)

    store._atomic_write = controlled_atomic_write  # type: ignore[method-assign]
    append_started.set()
    store.append_message("User", message)


class _ListOnlyChatStore:
    """Test double that rejects every dedicated-chat operation except listing."""

    def __init__(self, chats: list[object]) -> None:
        self.chats = chats
        self.list_calls = 0

    def list_chats(self) -> list[object]:
        self.list_calls += 1
        return self.chats

    def load_messages(self) -> None:
        raise AssertionError("ChatRegistry must not load dedicated-chat messages.")


class FlowChatStoreTests(unittest.TestCase):
    """Verify Flow Chat keeps its own durable, corruption-tolerant history."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.store = FlowChatStore(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_messages_persist_in_order_in_the_separate_flow_directory(self) -> None:
        self.store.append_message("User", "First Flow message")
        self.store.append_message("AMADEUS", "Second Flow message")

        loaded = FlowChatStore(self.root).load_messages()

        self.assertEqual(
            [
                ("User", "First Flow message"),
                ("AMADEUS", "Second Flow message"),
            ],
            [(message.speaker, message.message) for message in loaded],
        )
        self.assertTrue(all(message.created_at for message in loaded))
        self.assertTrue((self.root / "data/flow_chat/flow_messages.jsonl").exists())
        self.assertFalse((self.root / "data/chats/flow_messages.jsonl").exists())

    def test_missing_and_malformed_rows_do_not_prevent_valid_messages_loading(self) -> None:
        self.assertEqual([], self.store.load_messages())
        self.store.messages_path.write_text(
            "\n".join(
                [
                    json.dumps({"speaker": "User", "message": "Valid", "created_at": "2026-07-27T00:00:00+00:00"}),
                    "not json",
                    json.dumps({"speaker": "User", "message": "Missing timestamp"}),
                    json.dumps(["not", "a", "record"]),
                ]
            ) + "\n",
            encoding="utf-8",
        )

        self.assertEqual(
            [FlowChatMessage("User", "Valid", "2026-07-27T00:00:00+00:00")],
            self.store.load_messages(),
        )

    def test_concurrent_appends_preserve_every_message(self) -> None:
        other_store = FlowChatStore(self.root)
        first_write_started = threading.Event()
        allow_first_write = threading.Event()
        second_write_started = threading.Event()
        errors: list[BaseException] = []

        original_atomic_write = self.store._atomic_write
        write_count = 0

        def controlled_atomic_write(content: str) -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 1:
                first_write_started.set()
                allow_first_write.wait(timeout=1)
            else:
                second_write_started.set()
            original_atomic_write(content)

        def append_message(store: FlowChatStore, message: str) -> None:
            try:
                store.append_message("User", message)
            except BaseException as error:
                errors.append(error)

        with patch.object(self.store, "_atomic_write", side_effect=controlled_atomic_write), patch.object(
            other_store, "_atomic_write", side_effect=controlled_atomic_write
        ):
            first = threading.Thread(target=append_message, args=(self.store, "First concurrent message"))
            first.start()
            self.assertTrue(first_write_started.wait(timeout=1))

            second = threading.Thread(target=append_message, args=(other_store, "Second concurrent message"))
            second.start()
            self.assertFalse(second_write_started.wait(timeout=0.1))
            allow_first_write.set()
            first.join()
            second.join()

        self.assertEqual([], errors)
        self.assertEqual(
            {"First concurrent message", "Second concurrent message"},
            {message.message for message in self.store.load_messages()},
        )

    def test_process_appends_preserve_every_message(self) -> None:
        context = multiprocessing.get_context("spawn")
        first_append_started = context.Event()
        first_write_started = context.Event()
        allow_first_write = context.Event()
        second_append_started = context.Event()
        second_write_started = context.Event()
        allow_second_write = context.Event()

        first = context.Process(
            target=_append_message_in_process,
            args=(
                str(self.root),
                "First process message",
                first_append_started,
                first_write_started,
                allow_first_write,
            ),
        )
        second = context.Process(
            target=_append_message_in_process,
            args=(
                str(self.root),
                "Second process message",
                second_append_started,
                second_write_started,
                allow_second_write,
            ),
        )
        try:
            first.start()
            self.assertTrue(first_append_started.wait(timeout=5))
            self.assertTrue(first_write_started.wait(timeout=5))

            second.start()
            self.assertTrue(second_append_started.wait(timeout=5))
            self.assertFalse(second_write_started.wait(timeout=0.2))
            allow_first_write.set()
            self.assertTrue(second_write_started.wait(timeout=5))
            allow_second_write.set()

            first.join(timeout=5)
            second.join(timeout=5)
            self.assertEqual(0, first.exitcode)
            self.assertEqual(0, second.exitcode)
        finally:
            allow_first_write.set()
            allow_second_write.set()
            first.join(timeout=5)
            second.join(timeout=5)
            if first.is_alive():
                first.terminate()
            if second.is_alive():
                second.terminate()

        self.assertEqual(
            {"First process message", "Second process message"},
            {message.message for message in self.store.load_messages()},
        )

    def test_failed_atomic_replacement_preserves_prior_history(self) -> None:
        self.store.append_message("User", "Saved before failure")

        with patch("flow_chat.flow_chat_store.os.replace", side_effect=OSError("replacement failed")):
            with self.assertRaises(OSError):
                self.store.append_message("User", "Lost message")

        self.assertEqual(
            ["Saved before failure"],
            [message.message for message in self.store.load_messages()],
        )

    def test_exchange_second_record_failure_preserves_prior_history(self) -> None:
        self.store.append_message("User", "Saved before exchange failure")

        with patch.object(self.store, "_now", side_effect=["2026-07-27T00:00:00+00:00", OSError("timestamp failed")]):
            with self.assertRaises(OSError):
                self.store.append_exchange("New Flow request", "New Flow response")

        self.assertEqual(
            ["Saved before exchange failure"],
            [message.message for message in self.store.load_messages()],
        )

    def test_failed_atomic_exchange_replacement_preserves_prior_history(self) -> None:
        self.store.append_message("User", "Saved before exchange replacement failure")

        with patch("flow_chat.flow_chat_store.os.replace", side_effect=OSError("replacement failed")):
            with self.assertRaises(OSError):
                self.store.append_exchange("New Flow request", "New Flow response")

        self.assertEqual(
            ["Saved before exchange replacement failure"],
            [message.message for message in self.store.load_messages()],
        )

    def test_storage_directory_cannot_escape_project_or_use_dedicated_chats(self) -> None:
        with self.assertRaises(ValueError):
            FlowChatStore(self.root, "../outside")
        with self.assertRaises(ValueError):
            FlowChatStore(self.root, "data/chats")
        with self.assertRaises(ValueError):
            FlowChatStore(self.root, "data/chats/nested")


class ChatRegistryTests(unittest.TestCase):
    """Verify Flow sees current dedicated-chat metadata and never message bodies."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.chat_store = ChatHistoryStore(self.root)
        self.registry = ChatRegistry(self.chat_store)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_registry_projects_only_frozen_metadata_and_never_loads_messages(self) -> None:
        chat = self.chat_store.create_chat(
            "Private project", "Keep this description.", priority="Important", purpose="Project", scope="Project"
        )
        self.chat_store.append_message("User", "Dedicated message body must stay private.", chat.chat_id)

        list_only_store = _ListOnlyChatStore(self.chat_store.list_chats())
        metadata = ChatRegistry(list_only_store).get_chat_metadata(chat.chat_id)  # type: ignore[arg-type]

        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(1, list_only_store.list_calls)
        self.assertEqual(
            ["chat_id", "title", "description", "priority", "purpose", "scope"],
            [field.name for field in fields(metadata)],
        )
        self.assertEqual("Private project", metadata.title)
        self.assertEqual("Important", metadata.priority)
        self.assertEqual("Project", metadata.purpose)
        self.assertEqual("Project", metadata.scope)
        self.assertNotIn("Dedicated message body must stay private.", repr(metadata))
        with self.assertRaises(AttributeError):
            getattr(metadata, "message")

    def test_missing_description_and_live_chat_mutations_are_reflected(self) -> None:
        main = self.registry.get_chat_metadata("main")
        self.assertIsNotNone(main)
        assert main is not None
        self.assertEqual("", main.description)
        self.assertEqual("Normal", main.priority)
        self.assertEqual("General", main.purpose)
        self.assertEqual("Local", main.scope)

        created = self.chat_store.create_chat("Draft", "Initial description")
        self.assertEqual("Draft", self.registry.get_chat_metadata(created.chat_id).title)  # type: ignore[union-attr]

        self.chat_store.update_chat_metadata(created.chat_id, title="Renamed", description="Updated description")
        renamed = self.registry.get_chat_metadata(created.chat_id)
        self.assertEqual("Renamed", renamed.title)  # type: ignore[union-attr]
        self.assertEqual("Updated description", renamed.description)  # type: ignore[union-attr]

        self.chat_store.delete_chat(created.chat_id)
        self.assertIsNone(self.registry.get_chat_metadata(created.chat_id))
        self.assertEqual(self.registry.list_chat_metadata(), self.registry.get_relevant_chat_metadata())

    def test_legacy_metadata_rows_default_invalid_or_missing_typed_fields(self) -> None:
        self.chat_store.index_path.write_text(
            json.dumps(
                {
                    "current_chat_id": "legacy",
                    "chats": [{
                        "chat_id": "legacy", "title": "Legacy",
                        "created_at": "2026-07-27T00:00:00+00:00", "updated_at": "2026-07-27T00:00:00+00:00",
                        "priority": "Urgent", "purpose": 12, "scope": "Universe",
                    }],
                }
            ),
            encoding="utf-8",
        )
        migrated = self.chat_store.get_chat("legacy")
        self.assertIsNotNone(migrated)
        assert migrated is not None
        self.assertEqual(("Normal", "General", "Local"), (migrated.priority, migrated.purpose, migrated.scope))

    def test_create_and_update_validate_typed_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid priority"):
            self.chat_store.create_chat("Bad", priority="Urgent")  # type: ignore[arg-type]
        chat = self.chat_store.create_chat("Typed", priority="Critical", purpose="Study", scope="Global")
        updated = self.chat_store.update_chat_metadata(chat.chat_id, priority="Low", purpose="Other", scope="Project")
        self.assertEqual(("Low", "Other", "Project"), (updated.priority, updated.purpose, updated.scope))
        with self.assertRaisesRegex(ValueError, "Invalid scope"):
            self.chat_store.update_chat_metadata(chat.chat_id, scope="Everywhere")  # type: ignore[arg-type]


class _FakeLLM:
    """Capture shared-chat prompts without calling an external model."""

    def __init__(self, response: str = "Flow answer", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.response


class FlowContextAndCoreTests(unittest.TestCase):
    """Verify Flow context isolation and its Core-owned request lifecycle."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_context_separates_flow_history_from_metadata_and_never_leaks_chat_messages(self) -> None:
        flow_store = FlowChatStore(self.root)
        flow_store.append_message("User", "Prior Flow request")
        chat_store = ChatHistoryStore(self.root)
        chat = chat_store.create_chat(
            "Private chat", "Private metadata description", priority="Critical", purpose="Development", scope="Global"
        )
        chat_store.append_message("User", "Dedicated secret body", chat.chat_id)

        bundle = FlowContextBuilder(flow_store, ChatRegistry(chat_store)).build_for_message("Current Flow request")

        self.assertEqual("[RECENT FLOW HISTORY]\nUser: Prior Flow request", bundle.recent_flow_history)
        self.assertIn("[AVAILABLE DEDICATED CHATS]", bundle.dedicated_chat_metadata)
        self.assertIn(chat.chat_id, bundle.dedicated_chat_metadata)
        self.assertIn("Private chat", bundle.dedicated_chat_metadata)
        self.assertIn("Private metadata description", bundle.dedicated_chat_metadata)
        self.assertIn("priority: Critical", bundle.dedicated_chat_metadata)
        self.assertIn("purpose: Development", bundle.dedicated_chat_metadata)
        self.assertIn("scope: Global", bundle.dedicated_chat_metadata)
        self.assertIn("descriptive in V1 only", bundle.dedicated_chat_metadata)
        self.assertNotIn("Dedicated secret body", bundle.dedicated_chat_metadata)
        self.assertIn("Do not claim to know, read, or have access", bundle.dedicated_chat_metadata)

    def test_context_formats_an_empty_registry_without_history(self) -> None:
        registry = ChatRegistry(_ListOnlyChatStore([]))  # type: ignore[arg-type]
        bundle = FlowContextBuilder(FlowChatStore(self.root), registry).build_for_message("hello")

        self.assertIsNone(bundle.recent_flow_history)
        self.assertIn("[AVAILABLE DEDICATED CHATS]", bundle.dedicated_chat_metadata)
        self.assertIn("No dedicated chats", bundle.dedicated_chat_metadata)

    def test_flow_history_event_is_emitted_only_after_history_load_without_body_text(self) -> None:
        flow_store = FlowChatStore(self.root)
        flow_store.append_message("User", "Private earlier Flow body")
        logger = TraceLogger()
        logger.start_session()

        FlowContextBuilder(flow_store, ChatRegistry(ChatHistoryStore(self.root))).build_for_message("Current request", trace_logger=logger)

        events = logger.get_trace_events()
        self.assertIn("Flow History Loaded", [event["title"] for event in events])
        self.assertNotIn("Private earlier Flow body", str(events))

    def test_fake_llm_receives_flow_context_but_never_dedicated_message_bodies(self) -> None:
        llm = _FakeLLM()
        core = AmadeusCore(llm_client=llm, project_root=self.root)
        private_chat = core.create_chat("Private project", "Metadata is visible.")
        core.chat_history_store.append_message("User", "Dedicated body must not leak.", private_chat.chat_id)

        core.handle_flow_message("First Flow message")
        core.handle_flow_message("Second Flow message")

        prompt = llm.prompts[-1]
        self.assertIn("[RECENT FLOW HISTORY]", prompt)
        self.assertIn("User: First Flow message", prompt)
        self.assertIn("[AVAILABLE DEDICATED CHATS]", prompt)
        self.assertIn("Private project", prompt)
        self.assertIn("Metadata is visible.", prompt)
        self.assertNotIn("Dedicated body must not leak.", prompt)

    def test_core_creates_and_edits_typed_chat_metadata(self) -> None:
        core = AmadeusCore(llm_client=_FakeLLM(), project_root=self.root)
        created = core.create_chat("Scoped", "Initial", priority="Important", purpose="Project", scope="Project")
        updated = core.update_chat_metadata(
            created.chat_id, title="Edited", description="Changed", priority="Low", purpose="Other", scope="Global"
        )
        self.assertEqual(
            ("Edited", "Changed", "Low", "Other", "Global"),
            (updated.title, updated.description, updated.priority, updated.purpose, updated.scope),
        )

    def test_successful_flow_events_are_ordered_and_share_one_run(self) -> None:
        llm = _FakeLLM()
        core = AmadeusCore(llm_client=llm, project_root=self.root)
        live_events: list[dict[str, object]] = []

        result = core.handle_flow_message("Hello Flow", event_listener=live_events.append)

        titles = [event["title"] for event in result["trace_events"]]
        self.assertEqual(
            [
                "Flow Request Received",
                "Flow Chat Work Plan",
                "Flow Context Started",
                "Dedicated Chat Registry Requested",
                "Dedicated Chat Registry Loaded",
                "Flow Context Complete",
                "Preparing Answer Through Configured LLM",
                "Response Composed",
                "Flow Response Stored",
                "Flow Output Returned",
            ],
            titles,
        )
        self.assertEqual(result["trace_events"], live_events)
        self.assertEqual(1, len({event["run_id"] for event in result["trace_events"]}))
        self.assertEqual(["Hello Flow", "Flow answer"], [message.message for message in core.flow_chat_store.load_messages()])
        self.assertIn("[AVAILABLE DEDICATED CHATS]", llm.prompts[0])

    def test_failed_flow_response_ends_failed_without_persisting(self) -> None:
        core = AmadeusCore(
            llm_client=_FakeLLM(error=OllamaClientError("private backend detail")),
            project_root=self.root,
        )

        result = core.handle_flow_message("Hello Flow")

        self.assertEqual("Flow Request Failed", result["trace_events"][-1]["title"])
        self.assertEqual("failed", result["trace_events"][-1]["status"])
        self.assertNotIn("private backend detail", str(result["trace_events"]))
        self.assertEqual("AMADEUS could not complete that Flow request. Please try again.", result["response"])
        self.assertEqual([], core.flow_chat_store.load_messages())

    def test_llm_failure_does_not_persist_when_trace_failure_observation_fails(self) -> None:
        core = AmadeusCore(
            llm_client=_FakeLLM(error=OllamaClientError("private backend detail")),
            project_root=self.root,
        )

        with patch.object(TraceLogger, "has_failed_event", side_effect=AssertionError("trace observation failed")):
            result = core.handle_flow_message("Hello Flow")

        self.assertEqual("failed", result["trace_events"][-1]["status"])
        self.assertEqual([], core.flow_chat_store.load_messages())

    def test_flow_failure_payload_and_terminal_event_are_sanitized(self) -> None:
        core = AmadeusCore(llm_client=_FakeLLM(), project_root=self.root)
        core.flow_context_builder.build_for_message = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private backend detail"))

        result = core.handle_flow_message("Hello Flow")

        self.assertEqual("AMADEUS could not complete that Flow request. Please try again.", result["response"])
        self.assertEqual("Flow Request Failed", result["trace_events"][-1]["title"])
        self.assertEqual("The Flow request could not be completed.", result["trace_events"][-1]["summary"])
        self.assertNotIn("private backend detail", str(result))


if __name__ == "__main__":
    unittest.main()
