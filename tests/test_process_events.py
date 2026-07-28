"""Tests for validated process events and legacy trace compatibility."""

import unittest

from amadeus_trace import BrainRole, ProcessEventEmitter, ProcessEventStatus, ProcessEventType, TraceLogger
from amadeus_chat.chat_module import AmadeusChatModule


class ProcessEventEmitterTests(unittest.TestCase):
    """Verify ordered delivery, validation, and listener isolation."""

    def test_start_emit_complete_delivers_ordered_events(self) -> None:
        received = []
        emitter = ProcessEventEmitter()
        emitter.subscribe(received.append)

        run_id = emitter.start_run(source_module="core", title="Request received", summary="Message received.")
        emitter.emit(
            source_module="context_builder",
            brain_role=BrainRole.ACTIVE,
            event_type=ProcessEventType.CONTEXT,
            status=ProcessEventStatus.COMPLETED,
            title="Context ready",
            summary="Selected context types: recent conversation.",
        )
        emitter.complete_run(title="Response returned", summary="Response returned to GUI.")

        self.assertEqual([1, 2, 3], [event.sequence for event in received])
        self.assertTrue(all(event.run_id == run_id for event in received))

    def test_listener_failure_does_not_stop_event_recording(self) -> None:
        emitter = ProcessEventEmitter()
        emitter.subscribe(lambda event: (_ for _ in ()).throw(RuntimeError("display failed")))

        emitter.start_run(source_module="core", title="Request received", summary="Message received.")

        self.assertEqual(1, len(emitter.events))

    def test_progress_and_metadata_are_validated_and_copied(self) -> None:
        emitter = ProcessEventEmitter()
        emitter.start_run(source_module="core", title="Request received", summary="Message received.")
        metadata = {"context_type": "recent_conversation"}
        event = emitter.emit(
            source_module="context_builder",
            brain_role=BrainRole.ACTIVE,
            event_type=ProcessEventType.CONTEXT,
            status=ProcessEventStatus.RUNNING,
            title="Context building",
            summary="Selecting context.",
            progress=0.5,
            metadata=metadata,
        )
        metadata["context_type"] = "private memory"

        self.assertEqual(0.5, event.progress)
        self.assertEqual("recent_conversation", event.metadata["context_type"])
        with self.assertRaises(ValueError):
            emitter.emit(
                source_module="core",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.STEP,
                status=ProcessEventStatus.RUNNING,
                title="Bad progress",
                summary="Invalid progress.",
                progress=1.1,
            )

    def test_invalid_enum_values_are_rejected(self) -> None:
        emitter = ProcessEventEmitter()
        emitter.start_run(source_module="core", title="Request received", summary="Message received.")

        with self.assertRaises(ValueError):
            emitter.emit(
                source_module="core",
                brain_role="active",  # type: ignore[arg-type]
                event_type=ProcessEventType.STEP,
                status=ProcessEventStatus.RUNNING,
                title="Invalid role",
                summary="Enum validation must reject strings.",
            )

    def test_completed_run_rejects_later_events_and_duplicate_terminals(self) -> None:
        emitter = ProcessEventEmitter()
        listener_errors = []

        def emit_from_terminal_listener(_event) -> None:
            if _event.status is not ProcessEventStatus.COMPLETED:
                return
            try:
                emitter.emit(
                    source_module="core",
                    brain_role=BrainRole.SYSTEM,
                    event_type=ProcessEventType.RESULT,
                    status=ProcessEventStatus.COMPLETED,
                    title="Listener result",
                    summary="Must not be recorded.",
                )
            except RuntimeError as error:
                listener_errors.append(str(error))

        emitter.subscribe(emit_from_terminal_listener)
        emitter.start_run(source_module="core", title="Request received", summary="Message received.")
        emitter.complete_run(title="Response returned", summary="Response returned to GUI.")

        with self.assertRaises(RuntimeError):
            emitter.emit(
                source_module="core",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Late result",
                summary="Must not be recorded.",
            )
        with self.assertRaises(RuntimeError):
            emitter.complete_run(title="Duplicate completion", summary="Must not be recorded.")
        with self.assertRaises(RuntimeError):
            emitter.fail_run(title="Conflicting failure", summary="Must not be recorded.")

        self.assertEqual(2, len(emitter.events))
        self.assertEqual(1, len(listener_errors))

    def test_failed_run_rejects_later_events_and_duplicate_terminals(self) -> None:
        emitter = ProcessEventEmitter()
        emitter.start_run(source_module="core", title="Request received", summary="Message received.")
        emitter.fail_run(title="Request failed", summary="A safe failure occurred.")

        with self.assertRaises(RuntimeError):
            emitter.emit(
                source_module="core",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.STEP,
                status=ProcessEventStatus.RUNNING,
                title="Late work",
                summary="Must not be recorded.",
            )
        with self.assertRaises(RuntimeError):
            emitter.fail_run(title="Duplicate failure", summary="Must not be recorded.")
        with self.assertRaises(RuntimeError):
            emitter.complete_run(title="Conflicting completion", summary="Must not be recorded.")

        self.assertEqual(2, len(emitter.events))


class TraceLoggerCompatibilityTests(unittest.TestCase):
    """Verify legacy trace calls remain renderable through the emitter facade."""

    def test_legacy_trace_text_and_payload_fields_are_preserved(self) -> None:
        logger = TraceLogger()
        logger.start_session()

        self.assertEqual("No trace events recorded.", logger.get_trace_text())
        self.assertEqual([], logger.get_trace_events())

        logger.add_event("routing", "Request Route", "Chat route selected.", level="success")

        event = logger.get_trace_events()[-1]
        self.assertIn("[Request Route]", logger.get_trace_text())
        self.assertIn("Level: success", logger.get_trace_text(mode="detailed"))
        self.assertEqual("routing", event["category"])
        self.assertEqual("Chat route selected.", event["message"])
        self.assertEqual("success", event["level"])
        self.assertEqual("completed", event["status"])
        self.assertEqual("decision", event["event_type"])

    def test_legacy_warning_level_remains_warning(self) -> None:
        logger = TraceLogger()
        logger.start_session()
        logger.add_event("module", "Partial result", "A fallback was used.", level="warning")

        self.assertEqual("warning", logger.get_trace_events()[-1]["level"])
        self.assertEqual("warning", logger.current_session.events[-1].level)

    def test_legacy_categories_are_preserved_in_payload_and_detail_text(self) -> None:
        logger = TraceLogger()
        logger.start_session()

        for category in ("file", "llm", "annotation", "module", "routing"):
            logger.add_event(category, f"{category} event", "Safe compatibility event.")

        events = logger.get_trace_events()
        detailed_text = logger.get_trace_text(mode="detailed")
        self.assertEqual(["file", "llm", "annotation", "module", "routing"], [event["category"] for event in events])
        for category in ("file", "llm", "annotation", "module", "routing"):
            self.assertIn(f"Category: {category}", detailed_text)

    def test_terminal_lifecycle_calls_are_available_through_trace_logger(self) -> None:
        logger = TraceLogger()
        logger.start_session()

        logger.complete_run(title="Response Returned", summary="Response returned to the caller.")

        self.assertEqual("completed", logger.get_trace_events()[-1]["status"])


class ChatLifecycleTests(unittest.TestCase):
    """Verify Chat reports LLM boundaries without publishing prompt content."""

    def test_chat_emits_llm_request_and_response_boundaries(self) -> None:
        logger = TraceLogger()
        logger.start_session()
        chat = AmadeusChatModule(llm_client=type("Client", (), {"generate": lambda *_args, **_kwargs: "ok"})())

        self.assertEqual("ok", chat.handle_message("secret prompt", trace_logger=logger))

        self.assertEqual(["LLM Request", "LLM Response"], [event["title"] for event in logger.get_trace_events()])
        self.assertNotIn("secret prompt", str(logger.get_trace_events()))


if __name__ == "__main__":
    unittest.main()
