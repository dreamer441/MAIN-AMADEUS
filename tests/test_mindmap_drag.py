"""Regression coverage for responsive graph gestures and asynchronous position saves."""

import os
import threading
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QCoreApplication, QEvent, QPointF, Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from mindmap.gui.view import MindMapView
from mindmap.gui.physics import GraphPhysics
from mindmap.models import GraphNode, GraphSnapshot


class DelayedGraphCore:
    """Hold the first save so later pointer gestures overlap real worker activity."""

    def __init__(self):
        self.nodes = {
            'a': GraphNode('a', 'main', 'idea', 'A', position_x=-150),
            'b': GraphNode('b', 'main', 'idea', 'B', position_x=150),
        }
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.reads = 0
        self.fail_first = False
        self.listener = None

    def subscribe_mind_map(self, listener):
        self.listener = listener
        return lambda: setattr(self, 'listener', None)

    def get_mind_map_snapshot(self):
        self.reads += 1
        return GraphSnapshot('main', tuple(self.nodes.values()), ())

    def move_mind_map_node(self, node_id, x, y):
        self.calls.append((node_id, x, y))
        if len(self.calls) == 1:
            self.started.set()
            if not self.release.wait(5):
                raise RuntimeError('Test save gate timed out')
            if self.fail_first:
                raise RuntimeError('Simulated position save failure')
        self.nodes[node_id] = replace(self.nodes[node_id], position_x=x, position_y=y)
        if self.listener:
            self.listener({'event_type': 'node_updated', 'entity_id': node_id})
        return self.nodes[node_id]


class MindMapDragTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.core = DelayedGraphCore()
        self.view = MindMapView(self.core, refresh_on_init=False)
        self.view.resize(1100, 700)
        self.view._render_snapshot(self.core.get_mind_map_snapshot())
        self.view._stop_physics_motion()

    def tearDown(self):
        self.core.release.set()
        self.wait_until(lambda: not self.view.has_active_workers())
        self.view.close()
        self.view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def wait_until(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition(), 'GUI worker did not reach expected state')

    def move(self, x, y):
        self.view._begin_node_drag('a')
        self.view.node_items['a'].set_visual_position(x, y)
        self.view._update_node_drag('a', x, y)
        self.view._persist_node_position('a', x, y)

    def test_drag_pauses_physics_and_defers_external_refresh(self):
        self.view._begin_node_drag('a')
        self.assertFalse(self.view._physics_timer.isActive())
        self.view.node_items['a'].set_visual_position(123, 45)
        self.view._update_node_drag('a', 123, 45)
        reads = self.core.reads
        self.core.listener({'event_type': 'node_updated', 'entity_id': 'b'})
        self.app.processEvents()
        self.assertEqual(reads, self.core.reads)
        self.assertTrue(self.view.canvas.isEnabled())
        self.assertEqual(QPointF(123, 45), self.view.node_items['a'].pos())
        self.core.release.set()
        self.view._persist_node_position('a', 123, 45)
        self.wait_until(lambda: not self.view.has_active_workers())
        self.assertFalse(self.view._physics_timer.isActive())
        self.assertEqual((123, 45), (self.core.nodes['a'].position_x, self.core.nodes['a'].position_y))

    def test_slow_save_keeps_canvas_enabled_and_keeps_latest_drag(self):
        self.move(10, 20)
        self.assertTrue(self.core.started.wait(1))
        self.assertTrue(self.view.canvas.isEnabled())
        self.move(30, 40)
        self.move(70, 80)
        self.core.release.set()
        self.wait_until(lambda: not self.view.has_active_workers())
        self.assertEqual([('a', 10, 20), ('a', 70, 80)], self.core.calls)
        self.assertEqual(QPointF(70, 80), self.view.node_items['a'].pos())
        self.assertTrue(self.view.canvas.isEnabled())

    def test_failed_save_reports_error_and_does_not_drop_next_position(self):
        self.core.fail_first = True
        with patch.object(self.view, '_show_error') as report_error:
            self.move(10, 20)
            self.assertTrue(self.core.started.wait(1))
            self.move(90, 100)
            self.core.release.set()
            self.wait_until(lambda: not self.view.has_active_workers())
            report_error.assert_called_once()
        self.assertEqual((90, 100), (self.core.nodes['a'].position_x, self.core.nodes['a'].position_y))
        self.assertTrue(self.view.canvas.isEnabled())

    def test_snapshot_builds_positions_once_instead_of_once_per_node(self):
        original = GraphPhysics.positions
        calls = []
        def positions(physics):
            calls.append(len(physics.nodes))
            return original(physics)
        with patch.object(GraphPhysics, 'positions', positions):
            self.view._render_snapshot(self.core.get_mind_map_snapshot())
        self.assertEqual([2], calls)

    def test_close_drains_in_flight_and_queued_position_saves(self):
        self.move(10, 20)
        self.assertTrue(self.core.started.wait(1))
        self.move(50, 60)
        # Release the simulated slow disk while close runs its Qt event loop.
        QTimer.singleShot(20, self.core.release.set)
        self.view.close()
        self.assertFalse(self.view.has_active_workers())
        self.assertEqual([('a', 10, 20), ('a', 50, 60)], self.core.calls)
        self.assertEqual((50, 60), (self.core.nodes['a'].position_x, self.core.nodes['a'].position_y))

    def test_pointer_drag_moves_node_and_persists_release(self):
        self.view.show()
        self.app.processEvents()
        self.view._stop_physics_motion()
        item = self.view.node_items['a']
        original = QPointF(item.pos())
        viewport = self.view.canvas.viewport()
        start = self.view.canvas.mapFromScene(original)
        end = start + self.view.canvas.mapFromScene(QPointF(50, 35)) - self.view.canvas.mapFromScene(QPointF(0, 0))
        QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
        event = QMouseEvent(QEvent.Type.MouseMove, QPointF(end), QPointF(viewport.mapToGlobal(end)), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewport, event)
        self.assertGreater((item.pos() - original).manhattanLength(), 20)
        self.assertFalse(self.view._physics_timer.isActive())
        self.core.release.set()
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
        self.wait_until(lambda: not self.view.has_active_workers())
        self.assertTrue(self.core.calls)
        self.assertAlmostEqual(item.pos().x(), self.core.nodes['a'].position_x)
        self.assertAlmostEqual(item.pos().y(), self.core.nodes['a'].position_y)
