"""Focused storage and payload tests for AMADEUS chat comments."""

import json
import tempfile
import unittest
from pathlib import Path

from comments_module.comment_service import CommentService


class CommentsModuleTests(unittest.TestCase):
    """Verify comment types, editing, deletion, and panel formatting."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.service = CommentService(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_general_comment_has_annotation_type_and_clean_display(self) -> None:
        entry = self.service.add_comment("chat_1", "Revisit the architecture.")
        payload = self.service.build_panel_payload("chat_1")

        self.assertEqual("general", entry.comment_type)
        self.assertIsNone(entry.message_number)
        self.assertIn("Comment(A) - Revisit the architecture.", payload["content"])
        self.assertNotIn("Selection:", payload["content"])
        self.assertEqual([entry.to_dict()], payload["metadata"]["comments"])

    def test_selection_comment_can_be_edited_and_deleted(self) -> None:
        entry = self.service.add_comment("chat_1", "Needs review.", "[12] User: Selected text")
        updated = self.service.update_comment(entry.comment_id, "Reviewed.")

        self.assertEqual("selection", updated.comment_type)
        self.assertEqual(12, updated.message_number)
        self.assertIsNotNone(updated.updated_at)

        self.service.delete_comment(entry.comment_id)

        self.assertEqual([], self.service.list_for_chat("chat_1"))

    def test_comment_ids_do_not_repeat_after_deleting_a_middle_entry(self) -> None:
        first = self.service.add_comment("chat_1", "First note.")
        middle = self.service.add_comment("chat_1", "Middle note.")
        third = self.service.add_comment("chat_1", "Third note.")

        self.service.delete_comment(middle.comment_id)
        added = self.service.add_comment("chat_1", "Fourth note.")

        self.assertEqual("comment_0004", added.comment_id)
        self.assertEqual(
            {first.comment_id, third.comment_id, added.comment_id},
            {entry.comment_id for entry in self.service.list_for_chat("chat_1")},
        )

    def test_legacy_selection_record_infers_its_type(self) -> None:
        path = self.root / "data/comments/comments.json"
        path.write_text(json.dumps([{
            "comment_id": "comment_0001",
            "chat_id": "chat_1",
            "comment": "Legacy note.",
            "selected_text": "[4] User: Existing selection",
            "created_at": "2026-07-14T00:00:00+00:00",
            "message_number": 4,
        }]), encoding="utf-8")

        entry = self.service.list_for_chat("chat_1")[0]

        self.assertEqual("selection", entry.comment_type)
        self.service.add_comment("chat_1", "New general note.")
        raw_records = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("comment_type", raw_records[0])


if __name__ == "__main__":
    unittest.main()
