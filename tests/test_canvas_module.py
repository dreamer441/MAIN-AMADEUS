"""Focused domain and persistence tests for the Canvas module."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from canvas_module import (
    CANVAS_MODEL_PROFILES,
    CANVAS_SCHEMA_VERSION,
    CanvasConnector,
    CanvasConversationService,
    CanvasDocumentStore,
    CanvasModule,
    CanvasStorageError,
    CanvasTextBlock,
    CanvasWorkspaceDescriptor,
    CanvasWorkspaceRecord,
)
from llm_client import OllamaClient, OllamaClientError


class _FakeCanvasLLM:
    def __init__(self, response: str = "AMADEUS response", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, str | None]] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.calls.append((prompt, system_prompt))
        if self.error is not None:
            raise self.error
        return self.response


class _MutatingCanvasLLM(_FakeCanvasLLM):
    def __init__(self, module: CanvasModule) -> None:
        super().__init__(response="This response should not be committed")
        self.module = module

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        result = super().generate(prompt, system_prompt)
        self.module.create_text_block(text="Concurrent edit")
        return result


class _SequencedCanvasLLM(_FakeCanvasLLM):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(response="")
        self.responses = list(responses)

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.calls.append((prompt, system_prompt))
        if not self.responses:
            raise AssertionError("No fake Canvas response remains")
        return self.responses.pop(0)


class CanvasModuleTests(unittest.TestCase):
    def test_workspace_descriptor_reports_conversation_phase(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            descriptor = module.get_workspace_descriptor()

        self.assertIsInstance(descriptor, CanvasWorkspaceDescriptor)
        self.assertEqual("main", descriptor.workspace_id)
        self.assertEqual("Main Canvas", descriptor.title)
        self.assertEqual("conversation_ready", descriptor.status)
        self.assertEqual(CANVAS_SCHEMA_VERSION, descriptor.schema_version)

    def test_custom_workspace_id_is_preserved(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            descriptor = CanvasModule(Path(temporary_directory), workspace_id="brainstorm").get_workspace_descriptor()

        self.assertEqual("brainstorm", descriptor.workspace_id)

    def test_create_update_and_reload_text_block(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            created = module.create_text_block(text="First canvas idea", position_x=125.5, position_y=-44.0)
            updated = module.update_text_block(
                created.object_id,
                text="First canvas idea, refined",
                position_x=240.0,
                position_y=80.0,
            )
            reloaded = CanvasModule(project_root).get_snapshot()

        self.assertIsInstance(created, CanvasTextBlock)
        self.assertTrue(created.object_id.startswith("canvas_text_"))
        self.assertEqual(1, created.revision)
        self.assertEqual(2, updated.revision)
        self.assertEqual(2, reloaded.revision)
        self.assertEqual(1, len(reloaded.text_blocks))
        self.assertEqual("First canvas idea, refined", reloaded.text_blocks[0].text)
        self.assertEqual(240.0, reloaded.text_blocks[0].position_x)
        self.assertEqual(80.0, reloaded.text_blocks[0].position_y)
        self.assertEqual(created.object_id, reloaded.text_blocks[0].object_id)

    def test_create_update_and_reload_connector(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            source = module.create_text_block(text="Source")
            target = module.create_text_block(text="Target", position_x=500)
            created = module.create_connector(
                source_object_id=source.object_id,
                target_object_id=target.object_id,
                connector_type="arrow",
            )
            updated = module.update_connector(
                created.connector_id,
                connector_type="line",
                relation_type="supports",
                label="supports this",
                comment="The source provides evidence for the target.",
            )
            reloaded = CanvasModule(project_root).get_snapshot()

        self.assertIsInstance(created, CanvasConnector)
        self.assertTrue(created.connector_id.startswith("canvas_connector_"))
        self.assertEqual(1, created.revision)
        self.assertEqual(2, updated.revision)
        self.assertEqual(1, len(reloaded.connectors))
        connector = reloaded.connectors[0]
        self.assertEqual("line", connector.connector_type)
        self.assertEqual("supports", connector.relation_type)
        self.assertEqual("supports this", connector.label)
        self.assertEqual("The source provides evidence for the target.", connector.comment)
        self.assertEqual(source.object_id, connector.source_object_id)
        self.assertEqual(target.object_id, connector.target_object_id)

    def test_connector_endpoints_and_self_connections_are_validated(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            source = module.create_text_block(text="Only block")

            with self.assertRaises(KeyError):
                module.create_connector(source_object_id=source.object_id, target_object_id="missing")
            with self.assertRaises(ValueError):
                module.create_connector(source_object_id=source.object_id, target_object_id=source.object_id)

        self.assertEqual([], module.list_connectors())

    def test_moving_a_block_does_not_revise_its_connector(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            source = module.create_text_block(text="Source")
            target = module.create_text_block(text="Target")
            connector = module.create_connector(
                source_object_id=source.object_id,
                target_object_id=target.object_id,
            )
            module.update_text_block(source.object_id, position_x=420.0, position_y=90.0)
            reloaded = CanvasModule(project_root).get_snapshot()

        self.assertEqual(1, reloaded.connectors[0].revision)
        self.assertEqual(connector.connector_id, reloaded.connectors[0].connector_id)
        self.assertEqual(source.object_id, reloaded.connectors[0].source_object_id)
        self.assertEqual(target.object_id, reloaded.connectors[0].target_object_id)

    def test_delete_block_cascades_attached_connectors_atomically(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            first = module.create_text_block(text="A")
            second = module.create_text_block(text="B")
            third = module.create_text_block(text="C")
            attached = module.create_connector(source_object_id=first.object_id, target_object_id=second.object_id)
            preserved = module.create_connector(source_object_id=second.object_id, target_object_id=third.object_id)
            revision_before_delete = module.get_snapshot().revision

            deleted_blocks, deleted_connectors = module.delete_items(object_ids=[first.object_id])
            reloaded = CanvasModule(project_root).get_snapshot()

        self.assertEqual(1, deleted_blocks)
        self.assertEqual(1, deleted_connectors)
        self.assertEqual(revision_before_delete + 1, reloaded.revision)
        self.assertNotIn(first.object_id, {block.object_id for block in reloaded.text_blocks})
        self.assertNotIn(attached.connector_id, {item.connector_id for item in reloaded.connectors})
        self.assertIn(preserved.connector_id, {item.connector_id for item in reloaded.connectors})

    def test_delete_multiple_objects_is_persistent(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            first = module.create_text_block(text="A")
            second = module.create_text_block(text="B")
            module.create_connector(source_object_id=first.object_id, target_object_id=second.object_id)
            deleted = module.delete_objects([first.object_id, second.object_id])
            reloaded = CanvasModule(project_root).get_snapshot()

        self.assertEqual(2, deleted)
        self.assertEqual(0, len(reloaded.text_blocks))
        self.assertEqual(0, len(reloaded.connectors))

    def test_delete_connector_does_not_delete_blocks(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            source = module.create_text_block(text="Source")
            target = module.create_text_block(text="Target")
            connector = module.create_connector(source_object_id=source.object_id, target_object_id=target.object_id)
            deleted = module.delete_connectors([connector.connector_id])
            reloaded = CanvasModule(project_root).get_snapshot()

        self.assertEqual(1, deleted)
        self.assertEqual(2, len(reloaded.text_blocks))
        self.assertEqual(0, len(reloaded.connectors))

    def test_managed_projection_records_reject_public_edits_and_deletions(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            workspace = module.ensure_workspace("mindmap_projection", "Mind Map")
            first = CanvasTextBlock(
                object_id="managed-first",
                workspace_id=workspace.workspace_id,
                text="Managed first",
                position_x=0,
                position_y=0,
                locked=True,
                metadata={"mindmap_projection": True},
            )
            second = CanvasTextBlock(
                object_id="managed-second",
                workspace_id=workspace.workspace_id,
                text="Managed second",
                position_x=500,
                position_y=0,
                locked=True,
                metadata={"mindmap_projection": True},
            )
            connector = CanvasConnector(
                connector_id="managed-link",
                workspace_id=workspace.workspace_id,
                source_object_id=first.object_id,
                target_object_id=second.object_id,
                metadata={"mindmap_projection": True},
            )
            module._replace_mindmap_projection(
                workspace.workspace_id, blocks=(first, second), connectors=(connector,)
            )
            module.switch_workspace(workspace.workspace_id)

            with self.assertRaises(PermissionError):
                module.update_text_block(first.object_id, text="Change")
            with self.assertRaises(PermissionError):
                module.update_connector(connector.connector_id, label="Change")
            with self.assertRaises(PermissionError):
                module.delete_items(object_ids=[first.object_id])
            with self.assertRaises(PermissionError):
                module.delete_items(connector_ids=[connector.connector_id])

            self.assertEqual((first, second), module.get_snapshot().text_blocks)
            self.assertEqual((connector,), module.get_snapshot().connectors)

    def test_managed_projection_workspace_is_reserved_and_read_only(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            workspace = module.ensure_workspace("mindmap_projection", "Incorrect title")
            self.assertEqual("Mind Map", workspace.title)
            managed = CanvasTextBlock(
                object_id="managed-root",
                workspace_id=workspace.workspace_id,
                text="Managed root",
                position_x=0,
                position_y=0,
                metadata={"mindmap_projection": True},
            )
            module._replace_mindmap_projection(workspace.workspace_id, blocks=(managed,), connectors=())
            module.switch_workspace(workspace.workspace_id)

            with self.assertRaises(PermissionError):
                module.rename_workspace(workspace.workspace_id, "Changed")
            with self.assertRaises(PermissionError):
                module.delete_workspace(workspace.workspace_id)
            with self.assertRaises(PermissionError):
                module.create_text_block(text="Not allowed")
            with self.assertRaises(PermissionError):
                module.create_connector(source_object_id="first", target_object_id="second")
            with self.assertRaises(PermissionError):
                module.set_root_object(managed.object_id)
            with self.assertRaises(PermissionError):
                module.set_root_object(None)
            self.assertEqual("Mind Map", module.workspace_by_id("mindmap_projection").title)

    def test_managed_projection_selection_disables_canvas_edit_controls(self) -> None:
        from PyQt6.QtWidgets import QApplication

        from canvas_module.gui import CanvasView

        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            workspace = module.ensure_workspace("mindmap_projection", "Mind Map")
            block = CanvasTextBlock(
                object_id="managed-block",
                workspace_id=workspace.workspace_id,
                text="Managed projection",
                position_x=0,
                position_y=0,
                locked=True,
                metadata={"mindmap_projection": True},
            )
            module._replace_mindmap_projection(workspace.workspace_id, blocks=(block,), connectors=())
            module.switch_workspace(workspace.workspace_id)

            class Core:
                def __init__(self, canvas_module: CanvasModule) -> None:
                    self.canvas = canvas_module

                def get_canvas_workspace_descriptor(self):
                    return self.canvas.get_workspace_descriptor()

            application = QApplication.instance() or QApplication([])
            view = CanvasView(Core(module))
            view._items_by_id[block.object_id].setSelected(True)
            application.processEvents()

            self.assertFalse(view.edit_button.isEnabled())
            self.assertFalse(view.title_button.isEnabled())
            self.assertFalse(view.comment_button.isEnabled())
            self.assertFalse(view.delete_button.isEnabled())
            self.assertIn("read-only", view.status_label.text())
            view.close()

    def test_managed_projection_workspace_disables_workspace_and_creation_controls(self) -> None:
        from PyQt6.QtWidgets import QApplication

        from canvas_module.gui import CanvasView

        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            workspace = module.ensure_workspace("mindmap_projection", "Mind Map")
            module.switch_workspace(workspace.workspace_id)

            class Core:
                def __init__(self, canvas_module: CanvasModule) -> None:
                    self.canvas = canvas_module

                def get_canvas_workspace_descriptor(self):
                    return self.canvas.get_workspace_descriptor()

            application = QApplication.instance() or QApplication([])
            view = CanvasView(Core(module))
            application.processEvents()

            self.assertFalse(view.rename_workspace_button.isEnabled())
            self.assertFalse(view.delete_workspace_button.isEnabled())
            self.assertFalse(view.add_text_button.isEnabled())
            self.assertFalse(view.add_line_button.isEnabled())
            self.assertFalse(view.add_arrow_button.isEnabled())
            self.assertFalse(view.set_root_button.isEnabled())
            self.assertFalse(view.send_button.isEnabled())
            view.close()

    def test_canvas_mutations_publish_persisted_records(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            events: list[dict[str, object]] = []
            unsubscribe = module.subscribe(events.append)

            block = module.create_text_block(text="Canvas source")
            updated_block = module.update_text_block(block.object_id, text="Canvas source, updated")
            target = module.create_text_block(text="Target")
            connector = module.create_connector(
                source_object_id=block.object_id,
                target_object_id=target.object_id,
            )
            updated_connector = module.update_connector(connector.connector_id, label="supports")
            deleted_blocks, deleted_connectors = module.delete_items(object_ids=[block.object_id])
            unsubscribe()
            unsubscribe()
            module.create_text_block(text="Not published")

        self.assertEqual(
            [
                "canvas_block_saved",
                "canvas_block_saved",
                "canvas_block_saved",
                "canvas_connector_saved",
                "canvas_connector_saved",
                "canvas_items_deleted",
            ],
            [event["event_type"] for event in events],
        )
        self.assertIs(block, events[0]["block"])
        self.assertIs(updated_block, events[1]["block"])
        self.assertIs(target, events[2]["block"])
        self.assertIs(connector, events[3]["connector"])
        self.assertIs(updated_connector, events[4]["connector"])
        self.assertEqual(1, deleted_blocks)
        self.assertEqual(1, deleted_connectors)
        self.assertEqual([block.object_id], events[5]["deleted_object_ids"])
        self.assertEqual([connector.connector_id], events[5]["deleted_connector_ids"])

    def test_failed_or_no_op_mutations_do_not_publish_events(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            events: list[dict[str, object]] = []
            module.subscribe(events.append)

            with patch.object(module.store, "save", side_effect=CanvasStorageError("write failed")):
                with self.assertRaises(CanvasStorageError):
                    module.create_text_block(text="Not persisted")
            self.assertEqual((0, 0), module.delete_items(object_ids=["missing"]))

        self.assertEqual([], events)

    def test_undo_publishes_the_restored_snapshot_after_persistence(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            events: list[dict[str, object]] = []
            module.subscribe(events.append)
            block = module.create_text_block(text="Undo this")
            restored = module.undo_last_change()

        self.assertIsNotNone(restored)
        self.assertEqual("canvas_snapshot_restored", events[-1]["event_type"])
        self.assertIs(restored, events[-1]["snapshot"])
        self.assertNotIn(block.object_id, {item.object_id for item in restored.text_blocks})

    def test_empty_or_unknown_edits_are_rejected_without_rewriting(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            block = module.create_text_block(text="Keep this")

            with self.assertRaises(ValueError):
                module.update_text_block(block.object_id, text="   ")
            with self.assertRaises(KeyError):
                module.update_text_block("missing", text="No")
            with self.assertRaises(KeyError):
                module.update_connector("missing", label="No")

            snapshot = module.get_snapshot()

        self.assertEqual(1, snapshot.revision)
        self.assertEqual("Keep this", snapshot.text_blocks[0].text)

    def test_schema_v1_text_only_document_loads_and_migrates_on_next_save(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            path = project_root / "data" / "canvas" / "main.json"
            path.parent.mkdir(parents=True)
            block = CanvasTextBlock(
                object_id="canvas_text_legacy",
                workspace_id="main",
                text="Legacy idea",
                position_x=10,
                position_y=20,
            )
            legacy_payload = {
                "schema_version": 1,
                "workspace_id": "main",
                "revision": 4,
                "objects": [block.to_dict()],
            }
            path.write_text(json.dumps(legacy_payload), encoding="utf-8")

            module = CanvasModule(project_root)
            loaded = module.get_snapshot()
            migrated_path = project_root / "data" / "canvas" / "workspaces" / "main.json"
            still_legacy = json.loads(migrated_path.read_text(encoding="utf-8"))
            module.update_text_block(block.object_id, text="Legacy idea updated")
            migrated = json.loads(migrated_path.read_text(encoding="utf-8"))

        self.assertEqual(CANVAS_SCHEMA_VERSION, loaded.schema_version)
        self.assertEqual((), loaded.connectors)
        self.assertFalse(path.exists())
        self.assertEqual(1, still_legacy["schema_version"])
        self.assertEqual(CANVAS_SCHEMA_VERSION, migrated["schema_version"])
        self.assertEqual([], migrated["connectors"])

    def test_workspace_path_rejects_traversal(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            store = CanvasDocumentStore(Path(temporary_directory))
            with self.assertRaises(ValueError):
                store.path_for("../outside")

    def test_malformed_workspace_is_not_silently_overwritten(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            path = project_root / "data" / "canvas" / "main.json"
            path.parent.mkdir(parents=True)
            path.write_text("{broken", encoding="utf-8")
            module = CanvasModule(project_root)

            with self.assertRaises(CanvasStorageError):
                module.get_snapshot()
            migrated_path = project_root / "data" / "canvas" / "workspaces" / "main.json"
            self.assertFalse(path.exists())
            self.assertEqual("{broken", migrated_path.read_text(encoding="utf-8"))

    def test_connector_with_missing_reference_is_rejected_on_load(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            path = project_root / "data" / "canvas" / "main.json"
            path.parent.mkdir(parents=True)
            payload = {
                "schema_version": CANVAS_SCHEMA_VERSION,
                "workspace_id": "main",
                "revision": 1,
                "objects": [],
                "connectors": [
                    {
                        "connector_id": "broken",
                        "workspace_id": "main",
                        "source_object_id": "missing_a",
                        "target_object_id": "missing_b",
                        "connector_type": "arrow",
                    }
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(CanvasStorageError):
                CanvasModule(project_root).get_snapshot()

    def test_saved_document_has_explicit_schema_object_and_connector_types(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            source = module.create_text_block(text="Schema source")
            target = module.create_text_block(text="Schema target")
            module.create_connector(
                source_object_id=source.object_id,
                target_object_id=target.object_id,
                connector_type="arrow",
                relation_type="expands",
            )
            payload = json.loads((project_root / "data" / "canvas" / "workspaces" / "main.json").read_text(encoding="utf-8"))

        self.assertEqual(CANVAS_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual("main", payload["workspace_id"])
        self.assertEqual("text", payload["objects"][0]["object_type"])
        self.assertEqual("arrow", payload["connectors"][0]["connector_type"])
        self.assertEqual("expands", payload["connectors"][0]["relation_type"])

    def test_root_block_is_persistent_and_cleared_when_deleted(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            root = module.create_text_block(text="Central idea")
            module.set_root_object(root.object_id)
            reloaded = CanvasModule(project_root).get_snapshot()
            module.delete_objects([root.object_id])
            after_delete = CanvasModule(project_root).get_snapshot()

        self.assertEqual(root.object_id, reloaded.root_object_id)
        self.assertIsNone(after_delete.root_object_id)

    def test_schema_v2_document_loads_without_context_state_and_migrates(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            path = project_root / "data" / "canvas" / "main.json"
            path.parent.mkdir(parents=True)
            block = CanvasTextBlock(
                object_id="legacy_v2",
                workspace_id="main",
                text="Legacy connector-era block",
                position_x=0,
                position_y=0,
            )
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "workspace_id": "main",
                        "revision": 8,
                        "objects": [block.to_dict()],
                        "connectors": [],
                    }
                ),
                encoding="utf-8",
            )

            module = CanvasModule(project_root)
            loaded = module.get_snapshot()
            module.set_root_object(block.object_id)
            migrated_path = project_root / "data" / "canvas" / "workspaces" / "main.json"
            migrated = json.loads(migrated_path.read_text(encoding="utf-8"))

        self.assertIsNone(loaded.context_baseline)
        self.assertIsNone(loaded.root_object_id)
        self.assertEqual(CANVAS_SCHEMA_VERSION, migrated["schema_version"])
        self.assertEqual(block.object_id, migrated["root_object_id"])
        self.assertIsNone(migrated["context_baseline"])

    def test_first_preview_requires_explicit_target_without_baseline(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            block = module.create_text_block(text="First unsent idea")
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[block.object_id],
            )

        self.assertEqual((), preview.target_object_ids)
        self.assertTrue(any("No sent baseline" in warning for warning in preview.warnings))

    def test_explicit_selection_is_a_target_before_first_send(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            block = module.create_text_block(text="Please answer this")
            preview = module.build_context_preview(
                context_mode="selection",
                visible_object_ids=[block.object_id],
                selected_object_ids=[block.object_id],
            )

        self.assertEqual((block.object_id,), preview.target_object_ids)
        self.assertEqual("selection", preview.context_mode)

    def test_movement_after_baseline_is_not_a_semantic_target(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            block = module.create_text_block(text="Stable meaning")
            module.mark_current_state_sent()
            module.update_text_block(block.object_id, position_x=900, position_y=-300)
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[block.object_id],
            )

        self.assertEqual((), preview.target_object_ids)
        self.assertTrue(any("No new, edited" in warning for warning in preview.warnings))

    def test_text_edit_becomes_target_and_follows_incoming_arrow_to_root(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            root = module.create_text_block(text="Central starting idea")
            parent = module.create_text_block(text="Previous answer")
            target = module.create_text_block(text="Initial follow-up")
            unrelated = module.create_text_block(text="Other visible branch")
            module.create_connector(source_object_id=root.object_id, target_object_id=parent.object_id)
            module.create_connector(source_object_id=parent.object_id, target_object_id=target.object_id)
            module.create_connector(source_object_id=root.object_id, target_object_id=unrelated.object_id)
            module.set_root_object(root.object_id)
            module.mark_current_state_sent()
            module.update_text_block(target.object_id, text="New follow-up that needs an answer")

            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[root.object_id, parent.object_id, target.object_id, unrelated.object_id],
            )

        self.assertEqual((target.object_id,), preview.target_object_ids)
        self.assertEqual((parent.object_id, root.object_id), preview.ancestor_object_ids)
        self.assertNotIn(unrelated.object_id, preview.supporting_object_ids)
        self.assertIn(unrelated.object_id, preview.excluded_visible_object_ids)

    def test_plain_line_adds_equal_weight_peer_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Main changed idea")
            peer = module.create_text_block(text="Related token concern")
            module.create_connector(
                source_object_id=target.object_id,
                target_object_id=peer.object_id,
                connector_type="line",
            )
            module.mark_current_state_sent()
            module.update_text_block(target.object_id, text="Main changed idea, refined")
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[target.object_id, peer.object_id],
            )

        self.assertEqual((target.object_id,), preview.target_object_ids)
        self.assertEqual((peer.object_id,), preview.peer_object_ids)

    def test_changed_connector_is_target_and_includes_both_endpoints(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            source = module.create_text_block(text="Source")
            target = module.create_text_block(text="Target")
            connector = module.create_connector(
                source_object_id=source.object_id,
                target_object_id=target.object_id,
            )
            module.mark_current_state_sent()
            module.update_connector(connector.connector_id, label="new follow-up meaning")
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[source.object_id, target.object_id],
            )

        self.assertEqual({source.object_id, target.object_id}, set(preview.target_object_ids))
        self.assertEqual((connector.connector_id,), preview.target_connector_ids)

    def test_changed_connector_outside_viewport_is_not_a_target(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            visible = module.create_text_block(text="Visible idea")
            offscreen_source = module.create_text_block(text="Offscreen source")
            offscreen_target = module.create_text_block(text="Offscreen target")
            connector = module.create_connector(
                source_object_id=offscreen_source.object_id,
                target_object_id=offscreen_target.object_id,
            )
            module.mark_current_state_sent()
            module.update_connector(connector.connector_id, comment="Changed elsewhere")
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[visible.object_id],
            )

        self.assertEqual((), preview.target_connector_ids)
        self.assertEqual((), preview.target_object_ids)

    def test_viewport_boundary_blocks_offscreen_ancestor(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            root = module.create_text_block(text="Offscreen root")
            target = module.create_text_block(text="Visible target")
            module.create_connector(source_object_id=root.object_id, target_object_id=target.object_id)
            module.mark_current_state_sent()
            module.update_text_block(target.object_id, text="Visible changed target")
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[target.object_id],
            )

        self.assertEqual((target.object_id,), preview.target_object_ids)
        self.assertNotIn(root.object_id, preview.ancestor_object_ids)

    def test_branch_traversal_handles_arrow_cycles_without_duplicates(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            first = module.create_text_block(text="First")
            second = module.create_text_block(text="Second")
            third = module.create_text_block(text="Third")
            module.create_connector(source_object_id=first.object_id, target_object_id=second.object_id)
            module.create_connector(source_object_id=second.object_id, target_object_id=third.object_id)
            module.create_connector(source_object_id=third.object_id, target_object_id=first.object_id)
            preview = module.build_context_preview(
                context_mode="branch",
                visible_object_ids=[first.object_id, second.object_id, third.object_id],
                selected_object_ids=[second.object_id],
            )

        all_ids = (*preview.target_object_ids, *preview.supporting_object_ids)
        self.assertEqual(len(set(all_ids)), len(all_ids))
        self.assertEqual({first.object_id, second.object_id, third.object_id}, set(all_ids))

    def test_deletions_since_baseline_are_reported(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            first = module.create_text_block(text="Keep")
            removed = module.create_text_block(text="Remove")
            connector = module.create_connector(source_object_id=first.object_id, target_object_id=removed.object_id)
            module.mark_current_state_sent()
            module.delete_objects([removed.object_id])
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[first.object_id],
            )

        self.assertEqual((removed.object_id,), preview.deleted_object_ids)
        self.assertEqual((connector.connector_id,), preview.deleted_connector_ids)

    def test_context_budget_preserves_targets_and_trims_support(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            root = module.create_text_block(text="Root " + "r" * 500)
            target = module.create_text_block(text="Target " + "t" * 500)
            peer = module.create_text_block(text="Peer " + "p" * 1500)
            module.create_connector(source_object_id=root.object_id, target_object_id=target.object_id)
            module.create_connector(
                source_object_id=target.object_id,
                target_object_id=peer.object_id,
                connector_type="line",
            )
            module.mark_current_state_sent()
            module.update_text_block(target.object_id, text="Target edited " + "t" * 500)
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[root.object_id, target.object_id, peer.object_id],
                token_budget=300,
            )

        self.assertIn(target.object_id, preview.target_object_ids)
        self.assertIn(peer.object_id, preview.trimmed_object_ids)

    def test_canvas_conversation_commits_response_link_operation_and_baseline(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            root = module.create_text_block(text="Central idea")
            target = module.create_text_block(text="Initial follow-up")
            module.create_connector(source_object_id=root.object_id, target_object_id=target.object_id)
            module.set_root_object(root.object_id)
            module.mark_current_state_sent()
            module.update_text_block(target.object_id, text="Changed follow-up")
            client = _FakeCanvasLLM("A focused Canvas answer")
            service = CanvasConversationService(module, client)

            result = service.handle_request(
                instruction="Critique this",
                context_mode="viewport",
                visible_object_ids=[root.object_id, target.object_id],
                process_run_id="run_123",
            )
            snapshot = module.get_snapshot()

        self.assertTrue(result.succeeded)
        self.assertEqual("amadeus", result.response_block.created_by)
        self.assertEqual("responds_to", result.response_connector.relation_type)
        self.assertEqual(target.object_id, result.response_connector.source_object_id)
        self.assertEqual(result.response_block.object_id, result.response_connector.target_object_id)
        self.assertEqual("Critique this", result.send_operation.instruction)
        self.assertEqual("run_123", result.send_operation.process_run_id)
        self.assertEqual("_FakeCanvasLLM", result.send_operation.model_name)
        self.assertIn("CONTENT TO ANSWER", result.send_operation.prompt_text)
        self.assertNotIn(target.object_id, result.send_operation.prompt_text)
        self.assertEqual(1, len(snapshot.send_operations))
        self.assertEqual(snapshot.revision, snapshot.context_baseline.document_revision)
        self.assertIn(result.response_block.object_id, snapshot.context_baseline.object_fingerprints)
        self.assertIn("Critique this", client.calls[0][0])

    def test_empty_instruction_uses_natural_default_and_is_recorded_as_empty(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Please continue this idea")
            client = _FakeCanvasLLM("Natural continuation")
            service = CanvasConversationService(module, client)

            result = service.handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )

        self.assertTrue(result.succeeded)
        self.assertEqual("", result.send_operation.instruction)
        self.assertIn("directly and naturally", client.calls[0][0])

    def test_canvas_prompt_hides_internal_ids_and_machine_roles(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            root = module.create_text_block(text="Earlier idea")
            target = module.create_text_block(text="Give the exact RGB value")
            connector = module.create_connector(source_object_id=root.object_id, target_object_id=target.object_id)
            client = _FakeCanvasLLM("(86, 47, 55)")

            result = CanvasConversationService(module, client).handle_request(
                context_mode="selection",
                visible_object_ids=[root.object_id, target.object_id],
                selected_object_ids=[target.object_id],
            )

        prompt = client.calls[0][0]
        self.assertTrue(result.succeeded)
        self.assertIn("Give the exact RGB value", prompt)
        self.assertNotIn(root.object_id, prompt)
        self.assertNotIn(target.object_id, prompt)
        self.assertNotIn(connector.connector_id, prompt)
        self.assertNotIn("related_peer", prompt)
        self.assertNotIn("response_target", prompt)

    def test_internal_metadata_response_is_retried_once(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="What is the RGB value?")
            client = _SequencedCanvasLLM(
                [
                    f"The target object `{target.object_id}` is a response_target.",
                    "(86, 47, 55)",
                ]
            )

            result = CanvasConversationService(module, client).handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )

        self.assertTrue(result.succeeded)
        self.assertEqual("(86, 47, 55)", result.response)
        self.assertEqual(2, len(client.calls))
        self.assertIn("CORRECTION", client.calls[1][0])

    def test_repeated_internal_metadata_response_is_not_committed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Answer this directly")
            client = _SequencedCanvasLLM(
                [
                    "The target object is a related_peer.",
                    "Its parent connector points to a directional_ancestor.",
                ]
            )

            result = CanvasConversationService(module, client).handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )
            snapshot = module.get_snapshot()

        self.assertFalse(result.succeeded)
        self.assertEqual(1, len(snapshot.text_blocks))
        self.assertEqual((), snapshot.send_operations)

    def test_long_amadeus_response_uses_taller_initial_block(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Explain this")
            response = "Long explanation. " * 120

            result = CanvasConversationService(module, _FakeCanvasLLM(response)).handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )

        self.assertTrue(result.succeeded)
        self.assertEqual(420.0, result.response_block.width)
        self.assertGreater(result.response_block.height, 220.0)
        self.assertLessEqual(result.response_block.height, 760.0)

    def test_successful_canvas_response_is_not_a_new_target_after_baseline(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Answer this")
            result = CanvasConversationService(module, _FakeCanvasLLM()).handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )
            preview = module.build_context_preview(
                context_mode="viewport",
                visible_object_ids=[target.object_id, result.response_block.object_id],
            )

        self.assertEqual((), preview.target_object_ids)

    def test_llm_failure_does_not_mutate_canvas_or_advance_baseline(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Selected target")
            before = module.get_snapshot()
            service = CanvasConversationService(
                module,
                _FakeCanvasLLM(error=OllamaClientError("offline")),
            )

            result = service.handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )
            after = module.get_snapshot()

        self.assertFalse(result.succeeded)
        self.assertEqual(before, after)

    def test_concurrent_canvas_edit_rejects_stale_llm_response(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Selected target")
            service = CanvasConversationService(module, _MutatingCanvasLLM(module))

            result = service.handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )
            snapshot = module.get_snapshot()

        self.assertFalse(result.succeeded)
        self.assertIsInstance(result.error, RuntimeError)
        self.assertEqual(2, len(snapshot.text_blocks))
        self.assertEqual([], module.list_send_operations())
        self.assertIsNone(snapshot.context_baseline)

    def test_schema_v3_canvas_loads_without_send_operations(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            block = module.create_text_block(text="Legacy v3 block")
            path = module.store.path_for("main")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["schema_version"] = 3
            payload.pop("send_operations", None)
            path.write_text(json.dumps(payload), encoding="utf-8")

            snapshot = CanvasModule(project_root).get_snapshot()

        self.assertEqual(block.object_id, snapshot.text_blocks[0].object_id)
        self.assertEqual((), snapshot.send_operations)
        self.assertEqual(CANVAS_SCHEMA_VERSION, snapshot.schema_version)

    def test_undo_restores_complete_canvas_state_in_reverse_order(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            first = module.create_text_block(text="First")
            second = module.create_text_block(text="Second")
            connector = module.create_connector(
                source_object_id=first.object_id,
                target_object_id=second.object_id,
            )
            module.delete_objects([second.object_id])

            restored_delete = module.undo_last_change()
            restored_connector = module.undo_last_change()
            restored_second = module.undo_last_change()
            restored_first = module.undo_last_change()

        self.assertIsNotNone(restored_delete)
        self.assertEqual({first.object_id, second.object_id}, {block.object_id for block in restored_delete.text_blocks})
        self.assertEqual((connector.connector_id,), tuple(item.connector_id for item in restored_delete.connectors))
        self.assertEqual((), restored_connector.connectors)
        self.assertEqual((first.object_id,), tuple(block.object_id for block in restored_second.text_blocks))
        self.assertEqual((), restored_first.text_blocks)
        self.assertFalse(module.can_undo())

    def test_undo_removes_amadeus_response_link_operation_and_baseline_atomically(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Answer this")
            before_send = module.get_snapshot()
            result = CanvasConversationService(module, _FakeCanvasLLM("Direct answer")).handle_request(
                context_mode="selection",
                visible_object_ids=[target.object_id],
                selected_object_ids=[target.object_id],
            )
            restored = module.undo_last_change()

        self.assertTrue(result.succeeded)
        self.assertEqual(before_send.text_blocks, restored.text_blocks)
        self.assertEqual(before_send.connectors, restored.connectors)
        self.assertEqual(before_send.send_operations, restored.send_operations)
        self.assertEqual(before_send.context_baseline, restored.context_baseline)

    def test_prompt_handles_all_targets_and_preserves_connection_flow(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            australia = module.create_text_block(text="Australia has the planned capital Canberra.")
            estonia = module.create_text_block(text="Estonia is known for digital government.")
            question = module.create_text_block(text="What do these two countries have in common?")
            module.create_connector(source_object_id=australia.object_id, target_object_id=question.object_id)
            module.create_connector(source_object_id=estonia.object_id, target_object_id=question.object_id)
            extra_target = module.create_text_block(text="Also identify one important difference.")
            preview = module.build_context_preview(
                context_mode="selection",
                visible_object_ids=[
                    australia.object_id,
                    estonia.object_id,
                    question.object_id,
                    extra_target.object_id,
                ],
                selected_object_ids=[question.object_id, extra_target.object_id],
            )

            prompt = CanvasConversationService.build_prompt(preview)

        self.assertIn("CONTENT TO ANSWER — HANDLE EVERY ITEM", prompt)
        self.assertRegex(prompt, r"[12]\. What do these two countries have in common\?")
        self.assertRegex(prompt, r"[12]\. Also identify one important difference\.")
        self.assertIn("CONNECTION FLOW BETWEEN INCLUDED IDEAS", prompt)
        self.assertIn('"Australia has the planned capital Canberra." → "What do these two countries have in common?"', prompt)
        self.assertIn('"Estonia is known for digital government." → "What do these two countries have in common?"', prompt)
        self.assertIn("answer every one of them", prompt)



    def test_workspace_registry_restores_last_active_workspace(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            created = module.create_workspace("Game Design")
            reloaded = CanvasModule(project_root)
            reloaded_id = reloaded.workspace_id
            reloaded_title = reloaded.get_workspace_descriptor().title
            workspace_ids = {workspace.workspace_id for workspace in reloaded.list_workspaces()}

        self.assertEqual(created.workspace_id, reloaded_id)
        self.assertEqual("Game Design", reloaded_title)
        self.assertEqual({"main", created.workspace_id}, workspace_ids)

    def test_workspaces_keep_documents_and_send_state_separate(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            main_block = module.create_text_block(text="Main project idea")
            module.mark_current_state_sent()
            second = module.create_workspace("Second Project")
            second_block = module.create_text_block(text="Independent idea")
            second_snapshot = module.get_snapshot()
            module.switch_workspace("main")
            main_snapshot = module.get_snapshot()

        self.assertEqual((main_block.object_id,), tuple(block.object_id for block in main_snapshot.text_blocks))
        self.assertIsNotNone(main_snapshot.context_baseline)
        self.assertEqual((second_block.object_id,), tuple(block.object_id for block in second_snapshot.text_blocks))
        self.assertIsNone(second_snapshot.context_baseline)
        self.assertNotEqual(main_snapshot.workspace_id, second.workspace_id)

    def test_workspace_rename_preserves_stable_id_and_document(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            workspace = module.create_workspace("Original Name")
            block = module.create_text_block(text="Keep this content")
            renamed = module.rename_workspace(workspace.workspace_id, "Renamed Project")
            reloaded = CanvasModule(project_root)
            reloaded_id = reloaded.workspace_id
            reloaded_block_ids = tuple(item.object_id for item in reloaded.get_snapshot().text_blocks)

        self.assertEqual(workspace.workspace_id, renamed.workspace_id)
        self.assertEqual("Renamed Project", renamed.title)
        self.assertEqual(workspace.workspace_id, reloaded_id)
        self.assertEqual((block.object_id,), reloaded_block_ids)

    def test_delete_workspace_archives_document_and_selects_remaining_workspace(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            workspace = module.create_workspace("Temporary Project")
            module.create_text_block(text="Recoverable content")
            descriptor = module.delete_workspace(workspace.workspace_id)
            trash_files = list((project_root / "data" / "canvas" / "trash").glob(f"{workspace.workspace_id}_*.json"))
            workspaces = module.list_workspaces()
            archived_payload = json.loads(trash_files[0].read_text(encoding="utf-8"))

        self.assertEqual("main", descriptor.workspace_id)
        self.assertEqual(["main"], [item.workspace_id for item in workspaces])
        self.assertEqual(1, len(trash_files))
        self.assertEqual("Recoverable content", archived_payload["objects"][0]["text"])

    def test_deleting_only_workspace_creates_new_blank_main_canvas(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            module.create_text_block(text="Old main content")
            descriptor = module.delete_workspace("main")
            snapshot = module.get_snapshot()
            trash_files = list((project_root / "data" / "canvas" / "trash").glob("main_*.json"))

        self.assertEqual("main", descriptor.workspace_id)
        self.assertEqual("Main Canvas", descriptor.title)
        self.assertEqual((), snapshot.text_blocks)
        self.assertEqual(1, len(trash_files))

    def test_legacy_main_document_creates_registry_and_moves_into_workspace_folder(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            legacy_path = project_root / "data" / "canvas" / "main.json"
            legacy_path.parent.mkdir(parents=True)
            legacy_block = CanvasTextBlock(
                object_id="legacy_workspace_block",
                workspace_id="main",
                text="Legacy workspace content",
                position_x=0,
                position_y=0,
            )
            legacy_path.write_text(
                json.dumps(
                    {
                        "schema_version": CANVAS_SCHEMA_VERSION,
                        "workspace_id": "main",
                        "revision": 1,
                        "objects": [legacy_block.to_dict()],
                        "connectors": [],
                        "root_object_id": None,
                        "context_baseline": None,
                        "send_operations": [],
                    }
                ),
                encoding="utf-8",
            )
            module = CanvasModule(project_root)
            registry_payload = json.loads(
                (project_root / "data" / "canvas" / "registry.json").read_text(encoding="utf-8")
            )
            migrated_path = project_root / "data" / "canvas" / "workspaces" / "main.json"
            legacy_exists = legacy_path.exists()
            migrated_exists = migrated_path.exists()
            migrated_text = module.get_snapshot().text_blocks[0].text

        self.assertFalse(legacy_exists)
        self.assertTrue(migrated_exists)
        self.assertEqual("main", registry_payload["active_workspace_id"])
        self.assertEqual("Legacy workspace content", migrated_text)

    def test_undo_history_is_isolated_per_workspace(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            main_block = module.create_text_block(text="Main undo item")
            second = module.create_workspace("Second")
            second_block = module.create_text_block(text="Second undo item")
            module.switch_workspace("main")
            restored_main = module.undo_last_change()
            module.switch_workspace(second.workspace_id)
            restored_second = module.undo_last_change()

        self.assertEqual((), restored_main.text_blocks)
        self.assertNotIn(main_block.object_id, {item.object_id for item in restored_main.text_blocks})
        self.assertEqual((), restored_second.text_blocks)
        self.assertNotIn(second_block.object_id, {item.object_id for item in restored_second.text_blocks})

    def test_block_title_comment_and_anchor_persist(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            module = CanvasModule(project_root)
            block = module.create_text_block(
                text="Main content",
                title="Architecture",
                comment="Check this assumption",
                comment_anchor_degrees=42.5,
                comment_width=240.0,
                comment_height=96.0,
            )
            reloaded = CanvasModule(project_root).get_snapshot().text_blocks[0]

        self.assertEqual("Architecture", block.title)
        self.assertEqual("Check this assumption", reloaded.comment)
        self.assertAlmostEqual(42.5, reloaded.comment_anchor_degrees)
        self.assertEqual(240.0, reloaded.comment_width)
        self.assertEqual(96.0, reloaded.comment_height)
        self.assertEqual(6, CANVAS_SCHEMA_VERSION)

    def test_title_and_comment_are_semantic_but_comment_position_is_layout(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            block = module.create_text_block(text="Idea")
            module.mark_current_state_sent()
            module.update_text_block(
                block.object_id,
                comment_anchor_degrees=180.0,
                comment_width=260.0,
                comment_height=110.0,
            )
            position_only = module.context_builder.detect_changes(module.get_snapshot())
            module.update_text_block(block.object_id, title="New title")
            title_change = module.context_builder.detect_changes(module.get_snapshot())
            module.mark_current_state_sent()
            module.update_text_block(block.object_id, comment="New comment")
            comment_change = module.context_builder.detect_changes(module.get_snapshot())

        self.assertEqual((), position_only.changed_object_ids)
        self.assertIn(block.object_id, title_change.changed_object_ids)
        self.assertIn(block.object_id, comment_change.changed_object_ids)

    def test_canvas_model_weight_profiles_route_to_expected_ollama_models(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            service = CanvasConversationService(module, OllamaClient(model="llama3.2:latest"))
            light_client, light_name = service._client_for_weight("light")
            normal_client, normal_name = service._client_for_weight("normal")
            heavy_client, heavy_name = service._client_for_weight("heavy")

        self.assertEqual("qwen3:4b", CANVAS_MODEL_PROFILES["light"])
        self.assertEqual("qwen3:14b", normal_name)
        self.assertEqual("qwen3:32b", heavy_name)
        self.assertFalse(heavy_client.think)
        self.assertEqual(light_name, light_client.model)
        self.assertEqual(normal_name, normal_client.model)
        self.assertEqual(heavy_name, heavy_client.model)

    def test_ollama_client_can_disable_thinking_for_canvas_requests(self) -> None:
        client = OllamaClient(model="qwen3:32b", think=False)
        captured: dict[str, object] = {}

        def fake_post(path: str, payload: dict[str, object]) -> dict[str, object]:
            captured["path"] = path
            captured["payload"] = payload
            return {"response": "Direct answer"}

        client._post_json = fake_post  # type: ignore[method-assign]
        response = client.generate("Question", system_prompt="System")

        self.assertEqual("Direct answer", response)
        self.assertEqual("/api/generate", captured["path"])
        self.assertIs(False, captured["payload"]["think"])

    def test_unknown_canvas_model_weight_fails_without_mutating_canvas(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            target = module.create_text_block(text="Question")
            service = CanvasConversationService(module, _FakeCanvasLLM("Answer"))
            result = service.handle_request(
                context_mode="selection",
                selected_object_ids=[target.object_id],
                model_weight="impossible",
            )
            snapshot = module.get_snapshot()

        self.assertFalse(result.succeeded)
        self.assertEqual(1, len(snapshot.text_blocks))
        self.assertEqual((), snapshot.send_operations)

    def test_malformed_workspace_registry_is_preserved_and_not_recreated(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            registry_path = project_root / "data" / "canvas" / "registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text("{broken registry", encoding="utf-8")

            with self.assertRaises(CanvasStorageError):
                CanvasModule(project_root)
            preserved_registry = registry_path.read_text(encoding="utf-8")

        self.assertEqual("{broken registry", preserved_registry)

    def test_workspace_title_cannot_be_empty(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            with self.assertRaises(ValueError):
                module.create_workspace("   ")
            with self.assertRaises(ValueError):
                module.rename_workspace("main", "")
            workspace_ids = [workspace.workspace_id for workspace in module.list_workspaces()]

        self.assertEqual(["main"], workspace_ids)


if __name__ == "__main__":
    unittest.main()
