"""Behavioral checks for replaceable Core routes and isolated owner services."""

import ast
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from amadeus_core import AmadeusCore
from amadeus_core.module_registry import ModuleRegistry
from inner_brain import InnerBrainAnalysis
from permissions import PermissionGuard, PendingActionService


class ArchitectureBoundaryTests(unittest.TestCase):
    """Exercise ownership contracts without contacting a model or user storage."""

    def test_core_import_does_not_import_feature_modules_or_qt(self):
        result = subprocess.run([sys.executable, "-B", "-c",
            "import sys; import amadeus_core; "
            "assert 'PyQt6' not in sys.modules; "
            "assert 'amadeus_chat' not in sys.modules; "
            "assert 'storage' not in sys.modules; "
            "assert 'amadeus_app.composition' not in sys.modules"],
            capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_core_uses_current_registered_owner_and_preserves_request_arguments(self):
        calls = []
        def handle(*args, **kwargs):
            calls.append((args, kwargs))
            return {"response": "first"}
        registry = ModuleRegistry()
        registry.register("chat_workspace", SimpleNamespace(handle_user_message=handle))
        core = AmadeusCore(module_registry=registry)
        listener = lambda event: None
        first = core.handle_user_message("question", "context", listener, "short")
        self.assertEqual({"response": "first"}, first)
        self.assertEqual(("question", "context", listener, "short"), calls[0][0])
        registry.register("chat_workspace", SimpleNamespace(handle_user_message=lambda *a, **k: {"response": "replacement"}))
        self.assertEqual("replacement", core.handle_user_message("next")["response"])

    def test_canvas_routes_preserve_unspecified_update_fields(self):
        received = []
        canvas = SimpleNamespace(workspace_id="one", update_text_block=lambda *a, **k: received.append((a, k)))
        registry = ModuleRegistry()
        registry.register("canvas", canvas)
        core = AmadeusCore(module_registry=registry)
        core.canvas.update_text_block("block", title="New title")
        self.assertEqual([(("block",), {"title": "New title"})], received)
        self.assertEqual("one", core.canvas.workspace_id)
        canvas.workspace_id = "two"
        self.assertEqual("two", core.canvas.workspace_id)

    def test_habit_routes_and_flow_share_one_persisted_service(self):
        class Model:
            def generate(self, *args, **kwargs):
                return "answer"
        class Brain:
            def analyze_message(self, *args, **kwargs):
                return InnerBrainAnalysis()
        with tempfile.TemporaryDirectory() as directory:
            core = AmadeusCore(project_root=Path(directory), llm_client=Model(), inner_brain_service=Brain())
            task_id = core.habits.add_one_time_task("GUI-routed task", "2026-09-12")
            tasks = core.habit_tracker_service.day_overview("2026-09-12")["one_time_tasks"]
            self.assertEqual(task_id, tasks[0]["id"])
            self.assertIs(core.habits.module_registry.require("habit_tracker"), core.habit_tracker_service)
            flow = core.module_registry.require("flow_requests")
            self.assertIs(core.flow_habit_requests, flow.flow_habit_requests)

    def test_approval_guard_freezes_scope_and_never_replays_owner_failure(self):
        current = ["chat-one"]
        attempts = []
        def failing_owner(action):
            attempts.append(action.linked_chat_id)
            raise RuntimeError("owner failed")
        guard = PermissionGuard(PendingActionService(), lambda: current[0])
        guard.register_handler("sheet", failing_owner)
        pending = guard.create_pending_action(kind="sheet", fields={"request": "plan"}, scope="chat")
        current[0] = "chat-two"
        with self.assertRaises(RuntimeError):
            guard.approve_pending_action(pending.action_id)
        with self.assertRaises(ValueError):
            guard.approve_pending_action(pending.action_id)
        self.assertEqual(["chat-one"], attempts)

    def test_core_has_no_feature_execution_imports(self):
        path = Path(__file__).resolve().parents[1] / "amadeus_core" / "core_coordinator.py"
        imports = [node.module for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(node, ast.ImportFrom)]
        forbidden = {"storage", "annotation_module", "llm_client", "inner_brain", "mindmap", "canvas_module", "habit_tracker"}
        self.assertFalse(forbidden.intersection(name.split(".")[0] for name in imports if name))


if __name__ == "__main__":
    unittest.main()
