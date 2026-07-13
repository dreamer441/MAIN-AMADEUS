"""Focused Materials service and Core routing tests."""

import tempfile
import unittest
from pathlib import Path

from amadeus_core.core import AmadeusCore
from export_module import ExportSelection, ExportedChatRecord
from materials_module import MaterialsService
from storage import ChatHistoryMessage


class _FakeExports:
    def __init__(self) -> None:
        self.record = ExportedChatRecord(
            export_id="export_chat_1", chat_id="chat_1", chat_title="Saved Chat",
            exported_at="2026-07-13T00:00:00+00:00", message_count=1,
            txt_path="data/exports/export_chat_1/Saved_Chat.txt",
            md_path="data/exports/export_chat_1/Saved_Chat.md",
            json_path="data/exports/export_chat_1/Saved_Chat.json",
        )
        self.removed: list[str] = []

    def list_exports(self):
        return [] if self.removed else [self.record]

    def resolve_selection(self, export_id, range_token=None, export_missing_chat=False):
        if export_id != self.record.export_id or self.removed:
            return None, "Missing export"
        message = ChatHistoryMessage("User", "Saved export text", "2026-07-13T00:00:00+00:00", 1)
        return ExportSelection(self.record, [message], "all"), None

    def build_prompt_context(self, selection):
        return "VERIFIED EXPORTED CHAT SEGMENT\nSaved export text"

    def build_materials_panel_payload(self, selection):
        return {"type": "materials", "title": "Export: Saved Chat", "content": "Saved export text", "metadata": {}}

    def remove_export(self, export_id):
        self.removed.append(export_id)


class MaterialsServiceTests(unittest.TestCase):
    """Verify managed files and exports stay explicit and safely bounded."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.exports = _FakeExports()
        self.service = MaterialsService(self.root, self.exports)
        (self.service.materials_directory / "notes.txt").write_text("Local material text", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lists_managed_files_and_exports_with_metadata(self) -> None:
        rows = self.service.list_materials()
        self.assertEqual(["material:notes.txt", "export:export_chat_1"], [row["id"] for row in rows])
        self.assertEqual("managed_file", rows[0]["type"])
        self.assertEqual("chat_export", rows[1]["type"])
        self.assertEqual("notes.txt", rows[0]["metadata"]["relative_path"])

    def test_open_and_preview_do_not_require_or_create_callable_context(self) -> None:
        preview = self.service.preview_material("material:notes.txt")
        opened = self.service.open_material("material:notes.txt")
        self.assertEqual("Local material text", preview["content"])
        self.assertEqual("Local material text", opened["content"])
        self.assertEqual("material:notes.txt", opened["metadata"]["selected_material_id"])

    def test_callable_context_and_removal_are_explicit(self) -> None:
        context = self.service.build_callable_context("material:notes.txt")
        self.assertIn("VERIFIED MANAGED MATERIAL", context)
        self.assertIn("Local material text", context)
        self.assertEqual("export:export_chat_1", self.service.material_reference("export:export_chat_1"))
        self.service.remove_material("export:export_chat_1")
        self.assertEqual(["export_chat_1"], self.exports.removed)
        self.service.remove_material("material:notes.txt")
        self.assertFalse((self.service.materials_directory / "notes.txt").exists())


class MaterialsCoreRouteTests(unittest.TestCase):
    """Verify Core obtains material context through the Materials public API."""

    def test_handle_material_message_routes_selected_context_once(self) -> None:
        core = object.__new__(AmadeusCore)
        contexts: list[str] = []
        core.materials_service = type("Materials", (), {"build_callable_context": lambda _self, material_id: f"context:{material_id}"})()
        core.handle_user_message = lambda message, callable_context=None: contexts.append(callable_context) or {"response": message}

        result = core.handle_material_message("material:notes.txt", "Question")

        self.assertEqual({"response": "Question"}, result)
        self.assertEqual(["context:material:notes.txt"], contexts)


if __name__ == "__main__":
    unittest.main()
