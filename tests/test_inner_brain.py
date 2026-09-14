"""Focused safety tests for the local Inner Brain boundary and Core integration."""

import tempfile
import unittest
from pathlib import Path

from amadeus_core import AmadeusCore
from inner_brain import InnerBrainAnalysis, InnerBrainService


class _FakeInnerClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, *_args, **_kwargs) -> str:
        return self.response


class _FakeChatClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        return "answer"


class InnerBrainServiceTests(unittest.TestCase):
    def test_strict_json_accepts_only_bounded_allow_lists(self) -> None:
        service = InnerBrainService(_FakeInnerClient(
            '{"read_annotation":"file","title":"title","description":"description",'
            '"short_bullets":["bullet one"],"detailed_summary":"details",'
            '"suggested_write_actions":["memory","delete"]}'
        ))

        analysis = service.analyze_message("show my project files", route="chat")

        self.assertEqual("file", analysis.read_annotation)
        self.assertEqual(("title", "description"), analysis.metadata_fields)
        self.assertEqual(("memory",), analysis.suggested_write_actions)

    def test_metadata_intent_accepts_only_bounded_fields(self) -> None:
        service = InnerBrainService(_FakeInnerClient(
            '{"read_annotation":"metadata","metadata_module":"memory_module",'
            '"metadata_document_kind":"future","metadata_mode":"answer"}'
        ))

        analysis = service.analyze_message("What is planned for memory?", route="chat")

        self.assertEqual("metadata", analysis.read_annotation)
        self.assertEqual("memory_module", analysis.metadata_module)
        self.assertEqual("future", analysis.metadata_document_kind)
        self.assertEqual("answer", analysis.metadata_mode)

        invalid = InnerBrainService(_FakeInnerClient(
            '{"read_annotation":"metadata","metadata_module":"../memory_module",'
            '"metadata_document_kind":"README.md","metadata_mode":"delete"}'
        )).analyze_message("What is planned for memory?", route="chat")
        self.assertEqual("metadata", invalid.read_annotation)
        self.assertEqual("", invalid.metadata_module)
        self.assertEqual("", invalid.metadata_document_kind)
        self.assertEqual("", invalid.metadata_mode)

        flow = service.analyze_message("What is planned for memory?", route="flow")
        self.assertEqual("", flow.read_annotation)
        self.assertEqual("", flow.metadata_module)

    def test_invalid_json_and_unknown_actions_return_safe_empty_analysis(self) -> None:
        self.assertEqual("", InnerBrainService(_FakeInnerClient("not json")).analyze_message("hello").read_annotation)
        analysis = InnerBrainService(_FakeInnerClient('{"read_annotation":"shell","suggested_write_actions":["create"]}')).analyze_message("hello")
        self.assertEqual("", analysis.read_annotation)
        self.assertEqual(("create",), analysis.suggested_write_actions)

    def test_core_uses_existing_safe_read_handler_and_never_executes_write_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            primary = _FakeChatClient()
            inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: InnerBrainAnalysis(
                read_annotation="file", suggested_write_actions=("memory",), model="fake"
            )})()
            core = AmadeusCore(llm_client=primary, project_root=Path(directory), inner_brain_service=inner)
            result = core.handle_user_message("show project files")

        self.assertIn("SAFE INFERRED READ CONTEXT", primary.prompts[-1])
        self.assertEqual(["memory"], result["side_panel"]["metadata"]["suggested_write_actions"])

    def test_plain_creation_candidate_returns_approval_without_owner_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            primary = _FakeChatClient()
            inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: InnerBrainAnalysis(
                title="Plan", creation_kind="sheet", model="fake"
            )})()
            core = AmadeusCore(llm_client=primary, project_root=Path(directory), inner_brain_service=inner)
            result = core.handle_user_message("Create a planning sheet")

            self.assertEqual([], core.sheet_service.list_sheets(chat_id=core.get_current_chat_id(), scope="chat"))
            approval = result["approval_request"]
            self.assertEqual("sheet", approval["kind"])
            self.assertEqual("", result["response"])
            core.approve_pending_action(approval["action_id"])
            self.assertEqual(1, len(core.sheet_service.list_sheets(chat_id=core.get_current_chat_id(), scope="chat")))

    def test_explicit_annotation_skips_inner_brain_inference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            primary = _FakeChatClient()
            inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError())})()
            core = AmadeusCore(llm_client=primary, project_root=Path(directory), inner_brain_service=inner)
            result = core.handle_user_message("[file]")

        self.assertTrue(result["response"])

    def test_inferred_metadata_open_returns_memory_panel_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_metadata_module(root)
            primary = _FakeChatClient()
            inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: InnerBrainAnalysis(
                read_annotation="metadata",
                metadata_module="memory_module",
                metadata_document_kind="features",
                metadata_mode="open",
                model="fake",
            )})()
            core = AmadeusCore(llm_client=primary, project_root=root, inner_brain_service=inner)
            result = core.handle_user_message("show memory module features")

        self.assertEqual("memory", result["side_panel"]["type"])
        self.assertIn("memory_module/FEATURES.md", result["side_panel"]["content"])
        self.assertEqual([], primary.prompts)

    def test_inferred_metadata_answer_injects_exact_metadata_and_returns_panel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_metadata_module(root)
            primary = _FakeChatClient()
            inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: InnerBrainAnalysis(
                read_annotation="metadata",
                metadata_module="memory_module",
                metadata_document_kind="future",
                metadata_mode="answer",
                model="fake",
            )})()
            core = AmadeusCore(llm_client=primary, project_root=root, inner_brain_service=inner)
            result = core.handle_user_message("what is planned for memory?")

        self.assertIn("memory_module/FUTURE_UPDATES.md", primary.prompts[-1])
        self.assertEqual("memory", result["side_panel"]["type"])

    def test_flow_metadata_inference_neither_opens_nor_injects_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_metadata_module(root)
            primary = _FakeChatClient()
            inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: InnerBrainAnalysis(
                read_annotation="metadata",
                metadata_module="memory_module",
                metadata_document_kind="features",
                metadata_mode="open",
                model="fake",
            )})()
            core = AmadeusCore(llm_client=primary, project_root=root, inner_brain_service=inner)
            result = core.handle_flow_message("show memory module features")

        self.assertIsNone(result["side_panel"])
        self.assertNotIn("memory_module/FEATURES.md", primary.prompts[-1])

    @staticmethod
    def _write_metadata_module(root: Path) -> None:
        module = root / "memory_module"
        module.mkdir()
        (module / "README.md").write_text("# Memory\n", encoding="utf-8")
        (module / "FEATURES.md").write_text("memory features", encoding="utf-8")
        (module / "FUTURE_UPDATES.md").write_text("memory future", encoding="utf-8")


class InnerBrainMetadataTests(unittest.TestCase):
    def test_explicit_refresh_preserves_manual_fields_and_export_updates_reference_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = InnerBrainService(_FakeInnerClient(
                '{"title":"generated title","description":"generated description",'
                '"short_bullets":["bullet one"],"detailed_summary":"evidence"}'
            ))
            core = AmadeusCore(llm_client=_FakeChatClient(), project_root=Path(directory), inner_brain_service=service)
            chat = core.create_chat("Manual title", "Manual description")
            core.chat_history_store.append_message("User", "evidence", chat.chat_id)
            analysis = core.refresh_chat_inner_brain(chat.chat_id)
            updated = core.create_chat_inner_brain_export(chat.chat_id)

        self.assertEqual("generated title", analysis.title)
        self.assertEqual(("bullet one",), analysis.short_bullets)
        self.assertEqual("Manual title", updated.title)
        self.assertEqual("Manual description", updated.description)
        self.assertTrue(updated.inner_brain_analysis.export_id)


if __name__ == "__main__":
    unittest.main()
