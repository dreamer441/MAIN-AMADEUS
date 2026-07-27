"""Core-mediated persistence, event safety, and retrieval checks for Mind Map."""

import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from amadeus_core import AmadeusCore
from mindmap.repository import SQLiteMindMapRepository


class MindMapCoreTests(unittest.TestCase):
    """Verify Mind Map stays behind Core while retaining graph behavior."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.core = AmadeusCore(llm_client=object(), project_root=self.project_root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_core_registers_graph_crud_search_neighborhood_and_live_changes(self) -> None:
        changes = []
        self.core.subscribe_mind_map(changes.append)

        first = self.core.create_mind_map_node(title="First", description="Searchable graph object")
        second = self.core.create_mind_map_node(title="Second")
        third = self.core.create_mind_map_node(title="Third")
        link_one = self.core.create_mind_map_link(
            source_node_id=first.node_id,
            target_node_id=second.node_id,
        )
        self.core.create_mind_map_link(source_node_id=second.node_id, target_node_id=third.node_id)
        moved = self.core.move_mind_map_node(first.node_id, 125.0, -40.0)

        self.assertIs(self.core.mind_map_module, self.core.module_registry.get("mind_map"))
        self.assertEqual((125.0, -40.0), (moved.position_x, moved.position_y))
        self.assertEqual([first.node_id], [node.node_id for node in self.core.search_mind_map_nodes("searchable")])
        neighborhood = self.core.get_mind_map_neighborhood(first.node_id, depth=2)
        self.assertEqual({first.node_id, second.node_id, third.node_id}, {node.node_id for node in neighborhood.nodes})
        self.assertEqual(2, len(neighborhood.links))
        self.assertEqual("node_created", changes[0]["event_type"])

        self.core.delete_mind_map_link(link_one.link_id)
        self.core.delete_mind_map_node(second.node_id)
        snapshot = self.core.get_mind_map_snapshot()
        self.assertEqual({first.node_id, third.node_id}, {node.node_id for node in snapshot.nodes})
        self.assertEqual([], list(snapshot.links))
        self.assertEqual("node_deleted", changes[-1]["event_type"])

    def test_source_upsert_and_json_round_trip_use_core_wrappers(self) -> None:
        created = self.core.upsert_mind_map_source_node(
            source_type="sheet",
            source_id="sheet-1",
            title="Initial Sheet",
            node_type="sheet",
        )
        updated = self.core.upsert_mind_map_source_node(
            source_type="sheet",
            source_id="sheet-1",
            title="Renamed Sheet",
            node_type="sheet",
            description="Updated source metadata",
        )
        export_path = self.project_root / "graph.json"

        self.assertEqual(created.node_id, updated.node_id)
        self.assertEqual("Renamed Sheet", updated.title)
        self.assertEqual(export_path, self.core.export_mind_map(export_path))
        self.assertEqual("Renamed Sheet", json.loads(export_path.read_text(encoding="utf-8"))["nodes"][0]["title"])

        imported_core = AmadeusCore(llm_client=object(), project_root=self.project_root / "imported")
        imported = imported_core.import_mind_map(export_path)
        self.assertEqual(1, len(imported.nodes))
        self.assertEqual("Renamed Sheet", imported.nodes[0].title)

    def test_operation_events_are_ordered_terminal_and_private_data_safe(self) -> None:
        events = []
        node = self.core.create_mind_map_node(
            title="Private node title",
            content="private graph content",
            event_listener=events.append,
        )

        self.assertEqual([1, 2, 3], [event["sequence"] for event in events])
        self.assertEqual("completed", events[-1]["status"])
        self.assertEqual("Graph node was created and saved.", events[-2]["summary"])
        self.assertNotIn("Private node title", str(events))
        self.assertNotIn("private graph content", str(events))

        failed_events = []
        with self.assertRaises(ValueError):
            self.core.update_mind_map_node(node.node_id, title="   ", event_listener=failed_events.append)

        self.assertEqual([1, 2], [event["sequence"] for event in failed_events])
        self.assertEqual("failed", failed_events[-1]["status"])
        self.assertEqual("The graph operation could not be completed.", failed_events[-1]["summary"])
        self.assertIsNone(failed_events[-1]["details"])
        self.assertNotIn("title cannot be empty", str(failed_events))

    def test_graph_notifications_contain_identifiers_not_graph_content(self) -> None:
        changes = []
        self.core.subscribe_mind_map(changes.append)

        node = self.core.create_mind_map_node(
            title="Private title",
            description="Private description",
            content="Private content",
            metadata={"secret": "Private metadata"},
        )

        event = changes[-1]
        self.assertEqual(
            {"event_type", "entity_type", "entity_id", "graph_id", "created_at"}, set(event)
        )
        self.assertEqual(node.node_id, event["entity_id"])
        self.assertNotIn("Private", str(event))

    def test_replace_import_rolls_back_on_invalid_record_and_persistence_failure(self) -> None:
        original = self.core.create_mind_map_node(title="Existing graph")
        invalid_import = self.project_root / "invalid_graph.json"
        invalid_import.write_text(json.dumps({"nodes": [{"node_id": "broken"}], "links": []}), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.core.import_mind_map(invalid_import, replace_graph=True)
        self.assertEqual([original.node_id], [node.node_id for node in self.core.get_mind_map_snapshot().nodes])

        valid_import = self.project_root / "valid_graph.json"
        valid_import.write_text(
            json.dumps({"nodes": [{"node_id": "new", "title": "Replacement"}], "links": []}),
            encoding="utf-8",
        )
        with patch.object(self.core.mind_map_module.repository, "_insert_node", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.core.import_mind_map(valid_import, replace_graph=True)
        self.assertEqual([original.node_id], [node.node_id for node in self.core.get_mind_map_snapshot().nodes])

    def test_repository_database_path_cannot_escape_project_root(self) -> None:
        with self.assertRaises(ValueError):
            SQLiteMindMapRepository(self.project_root, "../outside.sqlite3")
        with self.assertRaises(ValueError):
            SQLiteMindMapRepository(self.project_root, str((self.project_root / "outside.sqlite3").resolve()))


class MindMapGuiWorkerTests(unittest.TestCase):
    """Verify long graph reads do not run on the GUI thread and controls recover."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.application = QApplication.instance() or QApplication([])

    def test_refresh_uses_worker_and_recovers_busy_controls(self) -> None:
        from mindmap.gui import MindMapView
        from mindmap.models import GraphSnapshot

        main_thread = threading.get_ident()

        class SlowCore:
            def __init__(self) -> None:
                self.called = threading.Event()
                self.release = threading.Event()
                self.thread_id = None

            def subscribe_mind_map(self, _listener) -> None:
                pass

            def get_mind_map_snapshot(self) -> GraphSnapshot:
                self.thread_id = threading.get_ident()
                self.called.set()
                self.release.wait(1)
                return GraphSnapshot(graph_id="main", nodes=(), links=())

        core = SlowCore()
        view = MindMapView(core)
        self.assertTrue(core.called.wait(1000))
        self.assertTrue(view._busy)
        self.assertTrue(all(not widget.isEnabled() for widget in view._busy_widgets))
        self.assertNotEqual(main_thread, core.thread_id)

        core.release.set()
        deadline = time.monotonic() + 1
        while view._busy and time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(0.01)
        self.assertFalse(view._busy)
        self.assertTrue(all(widget.isEnabled() for widget in view._busy_widgets))
        view.close()
        self.assertFalse(view.has_active_workers())


if __name__ == "__main__":
    unittest.main()
