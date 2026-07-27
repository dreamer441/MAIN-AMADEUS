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
from mindmap.gui.physics import GraphPhysics
from mindmap.models import GraphLink, GraphNode, GraphSnapshot
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

    def test_recent_node_retrieval_is_bounded_and_newest_first(self) -> None:
        first = self.core.create_mind_map_node(title="First")
        second = self.core.create_mind_map_node(title="Second")
        self.core.update_mind_map_node(first.node_id, description="Updated last")

        recent = self.core.mind_map_module.list_recent_nodes(1)

        self.assertEqual([first.node_id], [node.node_id for node in recent])
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            self.core.mind_map_module.list_recent_nodes(0)
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            self.core.mind_map_module.list_recent_nodes(101)

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

    def test_source_upsert_preserves_mindmap_view_metadata(self) -> None:
        created = self.core.upsert_mind_map_source_node(
            source_type="sheet", source_id="sheet-1", title="Sheet", node_type="sheet",
            metadata={"source_version": 1},
        )
        self.core.update_mind_map_node(
            created.node_id,
            metadata={"source_version": 1, "mindmap_pinned": True, "mindmap_central": True},
        )

        updated = self.core.upsert_mind_map_source_node(
            source_type="sheet", source_id="sheet-1", title="Updated", node_type="sheet",
            metadata={"source_version": 2, "mindmap_pinned": False},
        )

        self.assertEqual(2, updated.metadata["source_version"])
        self.assertTrue(updated.metadata["mindmap_pinned"])
        self.assertTrue(updated.metadata["mindmap_central"])

    def test_unsubscribe_stops_graph_notifications(self) -> None:
        changes = []
        unsubscribe = self.core.subscribe_mind_map(changes.append)
        self.core.create_mind_map_node(title="First")
        unsubscribe()
        self.core.create_mind_map_node(title="Second")

        self.assertEqual(1, len(changes))

    def test_batch_position_update_is_atomic_and_core_mediated(self) -> None:
        first = self.core.create_mind_map_node(title="First")
        second = self.core.create_mind_map_node(title="Second")
        repository = self.core.mind_map_module.repository

        with self.assertRaises(KeyError):
            repository.update_node_positions(
                "main", {first.node_id: (10.0, 20.0), "unknown": (30.0, 40.0)}
            )
        self.assertEqual((0.0, 0.0), (repository.get_node(first.node_id).position_x, repository.get_node(first.node_id).position_y))

        with patch.object(repository, "update_node_positions", wraps=repository.update_node_positions) as update_positions:
            self.core.move_mind_map_nodes({first.node_id: (10.0, 20.0), second.node_id: (30.0, 40.0)})
        self.assertEqual(1, update_positions.call_count)
        self.assertEqual((10.0, 20.0), (repository.get_node(first.node_id).position_x, repository.get_node(first.node_id).position_y))

    def test_pinned_node_position_cannot_be_persisted_through_core(self) -> None:
        node = self.core.create_mind_map_node(title="Pinned", metadata={"mindmap_pinned": True})

        moved = self.core.move_mind_map_node(node.node_id, 100.0, 200.0)

        self.assertEqual((0.0, 0.0), (moved.position_x, moved.position_y))
        persisted = self.core.get_mind_map_snapshot().nodes[0]
        self.assertEqual((0.0, 0.0), (persisted.position_x, persisted.position_y))

    def test_position_locked_node_cannot_be_moved_when_metadata_explicitly_unpins_it(self) -> None:
        node = self.core.create_mind_map_node(
            title="Locked",
            position_locked=True,
            metadata={"mindmap_pinned": False},
        )

        moved = self.core.move_mind_map_node(node.node_id, 100.0, 200.0)
        with self.assertRaisesRegex(ValueError, "cannot be moved"):
            self.core.move_mind_map_nodes({node.node_id: (300.0, 400.0)})

        self.assertEqual((0.0, 0.0), (moved.position_x, moved.position_y))
        persisted = self.core.get_mind_map_snapshot().nodes[0]
        self.assertEqual((0.0, 0.0), (persisted.position_x, persisted.position_y))

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
        self.assertFalse(view.canvas.isEnabled())
        self.assertNotEqual(main_thread, core.thread_id)

        core.release.set()
        deadline = time.monotonic() + 1
        while view._busy and time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(0.01)
        self.assertFalse(view._busy)
        self.assertTrue(all(widget.isEnabled() for widget in view._busy_widgets))
        self.assertTrue(view.canvas.isEnabled())
        view.close()
        self.assertFalse(view.has_active_workers())


class MindMapPhysicsTests(unittest.TestCase):
    """Verify force-layout projections stay deterministic and persistence-free."""

    def test_pinned_nodes_stay_fixed_and_relevance_increases_prominence(self) -> None:
        pinned = GraphNode(
            node_id="pinned", graph_id="main", node_type="idea", title="Pinned",
            importance=0.2, confidence=0.2, position_x=0, position_y=0,
            position_locked=True, metadata={"mindmap_pinned": False},
        )
        prominent = GraphNode(
            node_id="prominent", graph_id="main", node_type="feature", title="Prominent",
            importance=0.9, confidence=1.0, position_x=20, position_y=0,
        )
        snapshot = GraphSnapshot(
            graph_id="main", nodes=(pinned, prominent),
            links=(GraphLink("link", "main", "pinned", "prominent", "related_to", strength=1.0),),
        )

        physics = GraphPhysics(snapshot)
        physics.step(10)

        self.assertEqual((0, 0), physics.positions()["pinned"])
        self.assertGreater(physics.nodes["prominent"].radius, physics.nodes["pinned"].radius)

    def test_co_located_nodes_separate_with_deterministic_fallback_forces(self) -> None:
        first = GraphNode("first", "main", "idea", "First", position_x=0, position_y=0)
        second = GraphNode("second", "main", "idea", "Second", position_x=0, position_y=0)
        snapshot = GraphSnapshot(
            "main", (first, second),
            (GraphLink("link", "main", "first", "second", "related_to", strength=1.0),),
        )

        first_run = GraphPhysics(snapshot)
        second_run = GraphPhysics(snapshot)
        first_run.step()
        second_run.step()

        self.assertNotEqual(first_run.positions()["first"], first_run.positions()["second"])
        self.assertEqual(first_run.positions(), second_run.positions())


class MindMapGuiStateTests(unittest.TestCase):
    """Verify the ported panel and hover state without timer-dependent assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.application = QApplication.instance() or QApplication([])

    def test_grouped_node_list_actions_and_hover_context(self) -> None:
        from mindmap.gui import MindMapView

        class Core:
            def subscribe_mind_map(self, _listener) -> None:
                pass

        nodes = (
            GraphNode("task", "main", "task", "Task node", description="Stored task context"),
            GraphNode("idea", "main", "idea", "Idea node"),
        )
        view = MindMapView(Core(), refresh_on_init=False)
        view._render_snapshot(GraphSnapshot("main", nodes, ()))

        self.assertEqual(["Nodes", "Actions"], [view.left_tabs.tabText(index) for index in range(view.left_tabs.count())])
        self.assertEqual(["Context", "Node Details"], [view.right_tabs.tabText(index) for index in range(view.right_tabs.count())])
        self.assertEqual(["IDEA", "  Idea node", "TASK", "  Task node"], [view.node_list.item(index).text() for index in range(view.node_list.count())])
        self.assertTrue({"Pin Node", "Set as Central", "Force Layout"}.issubset(view.action_buttons))
        view._show_hover_context("task")
        self.assertIn("Stored task context", view.context_summary.toPlainText())
        view.close()

    def test_pinned_nodes_cannot_be_dragged_or_persisted(self) -> None:
        from PyQt6.QtWidgets import QGraphicsItem
        from mindmap.gui import MindMapView

        class Core:
            def subscribe_mind_map(self, _listener) -> None:
                pass

        node = GraphNode(
            "pinned", "main", "idea", "Pinned",
            position_locked=True,
            metadata={"mindmap_pinned": False},
        )
        view = MindMapView(Core(), refresh_on_init=False)
        view._render_snapshot(GraphSnapshot("main", (node,), ()))
        item = view.node_items[node.node_id]
        self.assertFalse(bool(item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable))
        with patch.object(view, "_run_core") as run_core:
            view._persist_node_position(node.node_id, 100.0, 200.0)
        run_core.assert_not_called()
        view.close()

    def test_view_unsubscribes_from_graph_notifications_when_closed(self) -> None:
        from mindmap.gui import MindMapView

        class Core:
            def __init__(self) -> None:
                self.unsubscribed = False

            def subscribe_mind_map(self, _listener):
                return lambda: setattr(self, "unsubscribed", True)

        core = Core()
        view = MindMapView(core, refresh_on_init=False)
        view.close()
        self.assertTrue(core.unsubscribed)

    def test_unchanged_snapshot_reconciles_existing_scene_items(self) -> None:
        from mindmap.gui import MindMapView

        class Core:
            def subscribe_mind_map(self, _listener) -> None:
                pass

        first = GraphNode("first", "main", "idea", "First", position_x=10, position_y=20)
        second = GraphNode("second", "main", "task", "Second", position_x=80, position_y=20)
        link = GraphLink("link", "main", "first", "second", "related_to")
        snapshot = GraphSnapshot("main", (first, second), (link,))
        view = MindMapView(Core(), refresh_on_init=False)
        view._render_snapshot(snapshot)
        node_item = view.node_items["first"]
        link_item = view.link_items["link"]

        with patch.object(view.scene, "clear") as clear_scene:
            view._render_snapshot(snapshot)

        clear_scene.assert_not_called()
        self.assertIs(node_item, view.node_items["first"])
        self.assertIs(link_item, view.link_items["link"])
        view.close()

    def test_visual_physics_timer_stops_after_stable_ticks(self) -> None:
        from mindmap.gui import MindMapView

        class Core:
            def subscribe_mind_map(self, _listener) -> None:
                pass

        first = GraphNode("first", "main", "idea", "First", position_locked=True)
        second = GraphNode("second", "main", "idea", "Second", position_locked=True, position_x=50)
        view = MindMapView(Core(), refresh_on_init=False)
        view._render_snapshot(GraphSnapshot("main", (first, second), ()))

        self.assertTrue(view._physics_timer.isActive())
        for _ in range(view.PHYSICS_SETTLE_TICKS):
            view._advance_physics()
        self.assertFalse(view._physics_timer.isActive())
        self.assertEqual(0.0, view.physics.nodes["first"].vx)
        view.close()

    def test_auto_layout_does_not_step_oversized_graph(self) -> None:
        from mindmap.gui import MindMapView

        class Core:
            def subscribe_mind_map(self, _listener) -> None:
                pass

        nodes = tuple(
            GraphNode(f"node-{index}", "main", "idea", f"Node {index}", position_x=index * 10)
            for index in range(MindMapView.MAX_AUTO_LAYOUT_NODES + 1)
        )
        view = MindMapView(Core(), refresh_on_init=False)
        view._render_snapshot(GraphSnapshot("main", nodes, ()))

        with patch.object(view.physics, "step") as step:
            view._auto_layout()

        step.assert_not_called()
        self.assertIn("limited", view.status_label.text())
        view.close()


if __name__ == "__main__":
    unittest.main()
