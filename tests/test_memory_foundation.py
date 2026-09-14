"""Focused tests for the additive structured Memory Module foundation."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memory_module import MemoryService
from memory_module.mindmap_projection import memory_brick_projection


class MemoryFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_legacy_jsonl_migrates_idempotently_without_changing_prompt_behavior(self) -> None:
        first = MemoryService(self.root)
        entry = first.store.add_global_memory("Keep explicit compatibility", source_chat_id="chat-1")

        second = MemoryService(self.root)
        brick = second.get_memory_brick(entry.memory_id)
        third = MemoryService(self.root)

        self.assertEqual([entry], second.list_global_memory())
        self.assertIn("Keep explicit compatibility", second.build_prompt_context("chat-1") or "")
        self.assertEqual("global", brick.scope_level)
        self.assertEqual(("user",), brick.domains)
        self.assertEqual(entry.memory_id, brick.evidence["legacy_memory_id"])
        with closing(sqlite3.connect(third.repository.database_path)) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM memory_bricks WHERE memory_id = ?", (entry.memory_id,)).fetchone()[0])

    def test_explicit_save_dual_writes_same_id_and_preserves_legacy_entry(self) -> None:
        service = MemoryService(self.root)

        entry = service.save_chat_memory("chat-7", "Use source-backed nodes")
        brick = service.get_memory_brick(entry.memory_id)

        self.assertEqual(entry, service.list_chat_memory("chat-7")[0])
        self.assertEqual(entry.memory_id, brick.memory_id)
        self.assertEqual("chat", brick.scope_level)
        self.assertEqual("chat-7", brick.scope_ref)
        self.assertEqual("explicit_user_action", brick.creation_source)

    def test_filtered_search_uses_structured_multi_value_labels_and_like_fallback(self) -> None:
        service = MemoryService(self.root)
        brick = service.create_memory_brick(
            "SQLite fallback finds percent 100% safely", domains=("chat", "project"),
            kinds=("fact", "decision"), categories=("Architecture", "Storage"), scope_level="chat", scope_ref="chat-1",
        )

        found = service.search_memory_bricks("100%", domains=("project",), kinds=("decision",), categories=("Storage",), scope_ref="chat-1")

        self.assertEqual([brick.memory_id], [row.memory_id for row in found])

    def test_source_registration_creates_five_pending_layers_and_hash_marks_them_stale(self) -> None:
        service = MemoryService(self.root)
        source = service.register_knowledge_source(
            source_type="sheet", owner_module="sheets_module", title="Plan", raw_locator="sheet-1", content_hash="first",
        )

        pending = service.list_knowledge_layers(source.source_id)
        stale = service.mark_source_layers_stale(source.source_id, "second")

        self.assertEqual(5, len(pending))
        self.assertEqual({"pending"}, {layer.status for layer in pending})
        self.assertEqual(5, len(stale))
        self.assertEqual({"stale"}, {layer.status for layer in stale})

    def test_projection_is_source_backed_and_does_not_own_mindmap_storage(self) -> None:
        service = MemoryService(self.root)
        brick = service.create_memory_brick("Project decision", scope_level="chat", scope_ref="chat-1")

        projection = memory_brick_projection(brick)

        self.assertEqual("memory_module", projection["source_module"])
        self.assertEqual(brick.memory_id, projection["source_id"])
        self.assertEqual("memory", projection["node_type"])
        self.assertEqual("chat-1", projection["source_locator"])


if __name__ == "__main__":
    unittest.main()
