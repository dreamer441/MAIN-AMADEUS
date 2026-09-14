"""Cross-module Mind Map workspace synchronization tests."""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from amadeus_core import AmadeusCore


class _CapturedLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompts.append(prompt)
        return "linked answer"


class MindMapWorkspaceSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.core = AmadeusCore(llm_client=object(), project_root=self.project_root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_new_chat_is_projected_without_bulk_importing_legacy_default_chat(self) -> None:
        self.assertEqual((), self.core.get_mind_map_snapshot().nodes)

        chat = self.core.create_chat(title="Architecture", description="Current architecture work")
        node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)

        self.assertIsNotNone(node)
        self.assertEqual("Architecture", node.title)
        self.assertEqual("chat", node.node_type)
        self.assertTrue(node.metadata["workspace_backed"])

    def test_chat_sheet_and_comment_creation_syncs_objects_and_links(self) -> None:
        chat = self.core.create_chat(title="Build Chat")
        chat_node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)
        sheet = self.core.create_sheet("Implementation", content="Use one public graph API.")
        comment = self.core.add_comment("Preserve source ownership.")

        sheet_node = self.core.mind_map_module.find_source_node("sheet", sheet.sheet_id)
        comment_node = self.core.mind_map_module.find_source_node("comment", comment.comment_id)
        snapshot = self.core.get_mind_map_snapshot()
        linked_pairs = {(link.source_node_id, link.target_node_id) for link in snapshot.links}

        self.assertIsNotNone(chat_node)
        self.assertIsNotNone(sheet_node)
        self.assertIsNotNone(comment_node)
        self.assertIn((chat_node.node_id, sheet_node.node_id), linked_pairs)
        self.assertIn((chat_node.node_id, comment_node.node_id), linked_pairs)
        self.assertEqual(chat.chat_id, sheet_node.source_reference.source_locator)
        self.assertEqual(chat.chat_id, comment_node.source_reference.source_locator)

    def test_workspace_typed_node_creates_real_sheet_and_default_chat_context(self) -> None:
        chat = self.core.create_chat(title="Planning")
        chat_node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)

        node = self.core.create_mind_map_workspace_node(
            title="Roadmap",
            node_type="sheet",
            content="Milestone one: stable chat-to-graph synchronization.",
            linked_chat_node_id=chat_node.node_id,
        )

        visible_sheets = self.core.list_sheets(scope="chat")
        linked_context = self.core.context_builder._build_chat_workspace_context(chat.chat_id)
        self.assertEqual(1, len(visible_sheets))
        self.assertEqual(node.source_reference.source_id, visible_sheets[0].sheet_id)
        self.assertIn("Title (literal): Roadmap", linked_context)
        self.assertIn("Node type (literal): sheet", linked_context)
        self.assertIn("Milestone one", linked_context)

    def test_linking_manual_workspace_node_materializes_it_unless_explicitly_disabled(self) -> None:
        chat = self.core.create_chat(title="Materialization")
        chat_node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)
        manual = self.core.create_mind_map_node(title="Manual Sheet", node_type="sheet", content="Create me")

        self.core.create_mind_map_link(source_node_id=chat_node.node_id, target_node_id=manual.node_id)
        materialized = self.core.mind_map_module.get_node(manual.node_id)
        self.assertEqual("sheet", materialized.source_reference.source_type)
        self.assertEqual(1, len(self.core.list_sheets(scope="chat")))

        graph_only = self.core.create_mind_map_workspace_node(
            title="Graph-only Sheet Label",
            node_type="sheet",
            content="Do not create a real sheet",
            create_workspace_object=False,
        )
        self.core.create_mind_map_link(source_node_id=chat_node.node_id, target_node_id=graph_only.node_id)
        graph_only = self.core.mind_map_module.get_node(graph_only.node_id)
        self.assertIsNone(graph_only.source_reference)
        self.assertTrue(graph_only.metadata["workspace_creation_disabled"])
        self.assertEqual(1, len(self.core.list_sheets(scope="chat")))

    def test_link_injection_can_be_disabled_per_relationship(self) -> None:
        chat = self.core.create_chat(title="Context Control")
        chat_node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)
        active = self.core.create_mind_map_node(title="Active Note", content="visible-context")
        hidden = self.core.create_mind_map_node(title="Hidden Note", content="hidden-context")
        self.core.create_mind_map_link(
            source_node_id=chat_node.node_id,
            target_node_id=active.node_id,
            metadata={"inject_into_chat": True},
        )
        self.core.create_mind_map_link(
            source_node_id=chat_node.node_id,
            target_node_id=hidden.node_id,
            metadata={"inject_into_chat": False},
        )

        context = self.core.mind_map_workspace_sync.build_linked_context(chat.chat_id)
        panel = self.core.get_linked_mind_map_panel_payload()

        self.assertIn("visible-context", context)
        self.assertNotIn("hidden-context", context)
        self.assertEqual(2, panel["metadata"]["count"])
        states = {row["title"]: row["inject_into_chat"] for row in panel["metadata"]["rows"]}
        self.assertEqual({"Active Note": True, "Hidden Note": False}, states)

    def test_linked_context_uses_literal_grounded_fields(self) -> None:
        chat = self.core.create_chat(title="Grounded Context")
        chat_node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)
        node = self.core.create_mind_map_node(
            title="test sheet v2",
            node_type="sheet",
            description="",
            content="4321\n1112",
            metadata={"workspace_creation_disabled": True},
        )
        self.core.create_mind_map_link(
            source_node_id=chat_node.node_id,
            target_node_id=node.node_id,
            link_type="contains",
        )

        context = self.core.mind_map_workspace_sync.build_linked_context(chat.chat_id)

        self.assertIn("[EXACT LINKED MIND MAP WORKSPACE DATA]", context)
        self.assertIn("Title (literal): test sheet v2", context)
        self.assertIn("Description (literal): <empty>", context)
        self.assertIn("<<<CONTENT\n4321\n1112\nCONTENT", context)
        self.assertIn("Never invent labels", context)
        self.assertNotIn("Project Goals", context)

    def test_deleting_source_backed_nodes_deletes_their_workspace_objects(self) -> None:
        chat = self.core.create_chat(title="Delete Sources")
        sheet = self.core.create_sheet("Disposable Sheet", content="remove sheet")
        comment = self.core.add_comment("remove comment")
        memory = self.core.memory_service.save_chat_memory(chat.chat_id, "remove memory")
        self.core.mind_map_workspace_sync.sync_memory(memory)

        source_records = (
            ("sheet", sheet.sheet_id),
            ("comment", comment.comment_id),
            ("memory", memory.memory_id),
        )
        for source_type, source_id in source_records:
            node = self.core.mind_map_module.find_source_node(source_type, source_id)
            self.assertIsNotNone(node)
            self.core.delete_mind_map_node(node.node_id)
            self.assertIsNone(self.core.mind_map_module.find_source_node(source_type, source_id))

        self.assertEqual([], self.core.list_sheets(scope="chat"))
        self.assertEqual([], self.core.comment_service.list_for_chat(chat.chat_id))
        self.assertEqual([], self.core.memory_service.list_chat_memory(chat.chat_id))

    def test_deleting_chat_node_deletes_the_real_chat(self) -> None:
        chat = self.core.create_chat(title="Disposable Chat")
        node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)

        self.core.delete_mind_map_node(node.node_id)

        self.assertIsNone(self.core.chat_history_store.get_chat(chat.chat_id))
        self.assertIsNone(self.core.mind_map_module.find_source_node("chat", chat.chat_id))
        self.assertIsNotNone(
            self.core.mind_map_module.find_source_node(
                "chat", self.core.chat_history_store.get_current_chat_id()
            )
        )

    def test_canvas_block_and_connector_project_to_source_backed_graph_records(self) -> None:
        first = self.core.canvas_module.create_text_block(text="First", title="Start")
        second = self.core.canvas_module.create_text_block(text="Second")
        connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
            relation_type="supports",
            label="evidence",
            comment="Canvas evidence",
        )

        first_node = self.core.mind_map_module.find_source_node("canvas_block", first.object_id)
        link = next(
            item
            for item in self.core.mind_map_module.list_links()
            if item.source_reference and item.source_reference.source_id == connector.connector_id
        )

        self.assertIsNotNone(first_node)
        self.assertEqual("canvas", first_node.node_type)
        self.assertEqual("Start", first_node.title)
        self.assertEqual("canvas_connector", link.source_reference.source_type)
        self.assertEqual("supports", link.link_type)
        self.assertEqual("evidence", link.label)
        self.assertEqual("Canvas evidence", link.evidence)

    def test_canvas_updates_upsert_one_source_node_and_link(self) -> None:
        first = self.core.canvas_module.create_text_block(text="First")
        second = self.core.canvas_module.create_text_block(text="Second")
        connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )

        updated_block = self.core.canvas_module.update_text_block(
            first.object_id, text="Updated", position_x=128.0, position_y=256.0
        )
        self.core.canvas_module.update_connector(
            connector.connector_id, relation_type="supports", label="updated evidence"
        )

        nodes = [
            node
            for node in self.core.mind_map_module.list_nodes()
            if node.source_reference
            and node.source_reference.source_type == "canvas_block"
            and node.source_reference.source_id == first.object_id
        ]
        links = [
            link
            for link in self.core.mind_map_module.list_links()
            if link.source_reference
            and link.source_reference.source_type == "canvas_connector"
            and link.source_reference.source_id == connector.connector_id
        ]

        self.assertEqual(1, len(nodes))
        self.assertEqual("Updated", nodes[0].content)
        self.assertEqual((128.0, 256.0), (nodes[0].position_x, nodes[0].position_y))
        self.assertEqual(updated_block.workspace_id, nodes[0].metadata["canvas_workspace_id"])
        self.assertEqual(1, len(links))
        self.assertEqual("supports", links[0].link_type)
        self.assertEqual("updated evidence", links[0].label)

    def test_canvas_response_commit_projects_response_block_and_connector(self) -> None:
        core = AmadeusCore(llm_client=_CapturedLLM(), project_root=self.project_root)
        target = core.canvas_module.create_text_block(text="Answer this Canvas question")

        result = core.handle_canvas_message(
            context_mode="selection",
            visible_object_ids=[target.object_id],
            selected_object_ids=[target.object_id],
        )

        response_block = result["canvas_response_block"]
        response_connector = result["canvas_response_connector"]
        response_node = core.mind_map_module.find_source_node(
            "canvas_block", response_block["object_id"]
        )
        response_link = next(
            (
                link
                for link in core.mind_map_module.list_links()
                if link.source_reference
                and link.source_reference.source_type == "canvas_connector"
                and link.source_reference.source_id == response_connector["connector_id"]
            ),
            None,
        )

        self.assertEqual("linked answer", result["response"])
        self.assertIsNotNone(response_node)
        self.assertEqual("amadeus", response_node.metadata["canvas_created_by"])
        self.assertIsNotNone(response_link)
        self.assertEqual("responds_to", response_link.link_type)

    def test_canvas_deletion_removes_projected_node_and_connector_link(self) -> None:
        first = self.core.canvas_module.create_text_block(text="First")
        second = self.core.canvas_module.create_text_block(text="Second")
        connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )

        self.assertIsNotNone(
            self.core.mind_map_module.find_source_node("canvas_block", first.object_id)
        )
        self.assertTrue(
            any(
                link.source_reference
                and link.source_reference.source_type == "canvas_connector"
                and link.source_reference.source_id == connector.connector_id
                for link in self.core.mind_map_module.list_links()
            )
        )
        self.core.canvas_module.delete_items(object_ids=[first.object_id])

        self.assertIsNone(
            self.core.mind_map_module.find_source_node("canvas_block", first.object_id)
        )
        self.assertFalse(
            any(
                link.source_reference
                and link.source_reference.source_type == "canvas_connector"
                and link.source_reference.source_id == connector.connector_id
                for link in self.core.mind_map_module.list_links()
            )
        )

    def test_deleting_canvas_backed_graph_node_deletes_canvas_block_and_connectors(self) -> None:
        first = self.core.canvas_module.create_text_block(text="First")
        second = self.core.canvas_module.create_text_block(text="Second")
        connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )
        node = self.core.mind_map_module.find_source_node("canvas_block", first.object_id)

        self.core.delete_mind_map_node(node.node_id)

        snapshot = self.core.canvas_module.get_snapshot()
        self.assertNotIn(first.object_id, {item.object_id for item in snapshot.text_blocks})
        self.assertNotIn(connector.connector_id, {item.connector_id for item in snapshot.connectors})
        self.assertIsNone(self.core.mind_map_module.find_source_node("canvas_block", first.object_id))
        self.assertFalse(
            any(
                link.source_reference
                and link.source_reference.source_type == "canvas_connector"
                and link.source_reference.source_id == connector.connector_id
                for link in self.core.mind_map_module.list_links()
            )
        )

    def test_deleting_canvas_backed_graph_link_deletes_canvas_connector(self) -> None:
        first = self.core.canvas_module.create_text_block(text="First")
        second = self.core.canvas_module.create_text_block(text="Second")
        connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )
        link = next(
            item
            for item in self.core.mind_map_module.list_links()
            if item.source_reference
            and item.source_reference.source_type == "canvas_connector"
            and item.source_reference.source_id == connector.connector_id
        )

        self.core.delete_mind_map_link(link.link_id)

        self.assertNotIn(
            connector.connector_id,
            {item.connector_id for item in self.core.canvas_module.get_snapshot().connectors},
        )
        self.assertIsNone(self.core.mind_map_module.get_link(link.link_id))

    def test_reverse_canvas_deletion_uses_source_workspace_and_restores_active_workspace(self) -> None:
        source_workspace = self.core.canvas_module.create_workspace("Source Workspace")
        first = self.core.canvas_module.create_text_block(text="First")
        second = self.core.canvas_module.create_text_block(text="Second")
        first_connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )
        third = self.core.canvas_module.create_text_block(text="Third")
        fourth = self.core.canvas_module.create_text_block(text="Fourth")
        second_connector = self.core.canvas_module.create_connector(
            source_object_id=third.object_id,
            target_object_id=fourth.object_id,
        )
        first_node = self.core.mind_map_module.find_source_node("canvas_block", first.object_id)
        second_link = next(
            link
            for link in self.core.mind_map_module.list_links()
            if link.source_reference
            and link.source_reference.source_type == "canvas_connector"
            and link.source_reference.source_id == second_connector.connector_id
        )
        self.core.canvas_module.switch_workspace("main")

        self.core.delete_mind_map_node(first_node.node_id)
        self.assertEqual("main", self.core.canvas_module.workspace_id)
        self.core.delete_mind_map_link(second_link.link_id)
        self.assertEqual("main", self.core.canvas_module.workspace_id)

        self.core.canvas_module.switch_workspace(source_workspace.workspace_id)
        source_snapshot = self.core.canvas_module.get_snapshot()

        self.assertNotIn(first.object_id, {block.object_id for block in source_snapshot.text_blocks})
        self.assertNotIn(first_connector.connector_id, {item.connector_id for item in source_snapshot.connectors})
        self.assertNotIn(second_connector.connector_id, {item.connector_id for item in source_snapshot.connectors})

    def test_canvas_snapshot_restore_reconciles_absent_source_records(self) -> None:
        first = self.core.canvas_module.create_text_block(text="First")
        second = self.core.canvas_module.create_text_block(text="Second")
        connector = self.core.canvas_module.create_connector(
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )

        self.core.canvas_module.undo_last_change()
        self.core.canvas_module.undo_last_change()

        self.assertIsNotNone(
            self.core.mind_map_module.find_source_node("canvas_block", first.object_id)
        )
        self.assertIsNone(
            self.core.mind_map_module.find_source_node("canvas_block", second.object_id)
        )
        self.assertFalse(
            any(
                link.source_reference
                and link.source_reference.source_type == "canvas_connector"
                and link.source_reference.source_id == connector.connector_id
                for link in self.core.mind_map_module.list_links()
            )
        )

    def test_slash_suggestions_expose_mindmap_annotation(self) -> None:
        insertions = {row["insert_text"] for row in self.core.get_annotation_suggestions("/")}
        self.assertIn("[mindmap]", insertions)

        guided = {row["insert_text"] for row in self.core.get_annotation_suggestions("[mindmap]")}
        self.assertIn("[mindmap] ", guided)
        self.assertIn("[mindmap][] ", guided)

    def test_memory_annotation_projects_new_memory_into_graph(self) -> None:
        chat = self.core.create_chat(title="Memory Chat")

        result = self.core.handle_user_message("[memory][chat] Keep graph provenance[end]")
        memories = self.core.memory_service.list_chat_memory(chat.chat_id)
        self.assertEqual(1, len(memories))
        node = self.core.mind_map_module.find_source_node("memory", memories[0].memory_id)

        self.assertIsNotNone(node)
        self.assertEqual("memory", node.node_type)
        self.assertIn("Saved to chat memory", result["response"])
        context = self.core.mind_map_workspace_sync.build_linked_context(chat.chat_id)
        self.assertIn("Keep graph provenance", context)

        self.core.update_mind_map_node(node.node_id, content="Keep exact graph provenance")
        updated_memory = self.core.memory_service.get_memory(memories[0].memory_id)
        self.assertEqual("Keep exact graph provenance", updated_memory.content)

    def test_approved_workspace_records_enter_dedicated_chat_linked_context(self) -> None:
        llm = _CapturedLLM()
        core = AmadeusCore(llm_client=llm, project_root=self.project_root)
        chat = core.create_chat(title="Linked Workspace")
        sheet = core.handle_user_message("[sheet][create] Sheet literal evidence")
        memory = core.handle_user_message("[memory][save] Memory literal evidence")
        core.approve_pending_action(sheet["approval_request"]["action_id"])
        core.approve_pending_action(memory["approval_request"]["action_id"])

        core.handle_user_message("What workspace evidence is linked?")
        prompt = llm.prompts[-1]

        self.assertEqual(chat.chat_id, core.get_current_chat_id())
        self.assertIn("Sheet literal evidence", prompt)
        self.assertIn("Memory literal evidence", prompt)
        self.assertIn("Source type: sheet", prompt)
        self.assertIn("Source type: memory", prompt)

    def test_global_flow_memory_has_no_chat_neighbor(self) -> None:
        core = AmadeusCore(llm_client=_CapturedLLM(), project_root=self.project_root)
        chat = core.create_chat(title="Unlinked Workspace")
        chat_node = core.mind_map_module.find_source_node("chat", chat.chat_id)

        result = core.handle_flow_message("[memory][save] Global note")
        core.approve_pending_action(result["approval_request"]["action_id"])
        memory = core.memory_service.list_global_memory()[0]
        memory_node = core.mind_map_module.find_source_node("memory", memory.memory_id)

        self.assertEqual(("global", None), (memory.scope, memory.source_chat_id))
        neighborhood = core.mind_map_module.get_neighborhood(chat_node.node_id, depth=1)
        self.assertEqual((), neighborhood.links)
        self.assertNotIn(memory_node.node_id, {node.node_id for node in neighborhood.nodes})

    def test_reconciliation_projects_eligible_source_nodes_as_locked_blocks(self) -> None:
        chat = self.core.create_chat(title="Projected Chat")
        sheet = self.core.create_sheet("Projected Sheet", content="sheet literal")
        comment = self.core.add_comment("comment literal")
        memory = self.core.memory_service.save_chat_memory(chat.chat_id, "memory literal")
        self.core.mind_map_workspace_sync.sync_memory(memory)
        canvas_block = self.core.canvas_module.create_text_block(text="canvas literal")

        self.core.mind_map_workspace_sync.reconcile_canvas_projection()

        workspace = self.core.canvas_module.workspace_by_id("mindmap_projection")
        snapshot = self.core.canvas_module.get_snapshot_for_workspace(workspace.workspace_id)
        projected_types = {block.metadata["source_type"] for block in snapshot.text_blocks}

        self.assertEqual({"chat", "sheet", "comment", "memory", "canvas_block"}, projected_types)
        self.assertTrue(all(block.locked for block in snapshot.text_blocks))
        self.assertEqual(
            {"mindmap_projection", "mindmap_node_id", "source_type", "source_id", "source_locator"},
            set(snapshot.text_blocks[0].metadata),
        )
        self.assertTrue(
            any(
                block.metadata["mindmap_node_id"]
                == self.core.mind_map_module.find_source_node("canvas_block", canvas_block.object_id).node_id
                for block in snapshot.text_blocks
            )
        )

    def test_reconciliation_projects_links_only_when_both_nodes_are_eligible(self) -> None:
        chat = self.core.create_chat(title="Linked Chat")
        sheet = self.core.create_sheet("Linked Sheet", content="literal")
        chat_node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)
        sheet_node = self.core.mind_map_module.find_source_node("sheet", sheet.sheet_id)
        graph_only = self.core.create_mind_map_node(title="Graph-only")
        projected_link = self.core.create_mind_map_link(
            source_node_id=chat_node.node_id,
            target_node_id=sheet_node.node_id,
            link_type="supports",
            label="evidence",
        )
        excluded_link = self.core.create_mind_map_link(
            source_node_id=chat_node.node_id,
            target_node_id=graph_only.node_id,
        )

        snapshot = self.core.canvas_module.get_snapshot_for_workspace("mindmap_projection")
        connector = next(
            item
            for item in snapshot.connectors
            if item.metadata.get("mindmap_link_id") == projected_link.link_id
        )

        self.assertEqual("supports", connector.relation_type)
        self.assertEqual("evidence", connector.label)
        self.assertTrue(connector.metadata["mindmap_projection"])
        self.assertNotIn(
            excluded_link.link_id,
            {item.metadata["mindmap_link_id"] for item in snapshot.connectors},
        )

    def test_reconciliation_removes_only_stale_managed_records(self) -> None:
        chat = self.core.create_chat(title="Disposable Projection")
        node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)

        self.core.delete_mind_map_node(node.node_id, delete_source=False)

        snapshot = self.core.canvas_module.get_snapshot_for_workspace("mindmap_projection")
        self.assertFalse(
            any(block.metadata.get("mindmap_node_id") == node.node_id for block in snapshot.text_blocks)
        )

    def test_managed_projection_records_are_read_only_and_do_not_reenter_canvas_bridge(self) -> None:
        chat = self.core.create_chat(title="Protected Projection")
        managed = self.core.canvas_module.get_snapshot_for_workspace("mindmap_projection").text_blocks[0]
        self.core.canvas_module.switch_workspace("mindmap_projection")

        with self.assertRaises(PermissionError):
            self.core.canvas_module.update_text_block(managed.object_id, text="change")
        with self.assertRaises(PermissionError):
            self.core.canvas_module.delete_items(object_ids=[managed.object_id])

        self.core.mind_map_workspace_sync.handle_canvas_event(
            {"event_type": "canvas_block_saved", "block": managed}
        )

        self.assertEqual("Protected Projection", chat.title)
        self.assertIsNone(self.core.mind_map_module.find_source_node("canvas_block", managed.object_id))

    def test_projection_workspace_events_cannot_contaminate_the_graph(self) -> None:
        from canvas_module.models import CanvasConnector, CanvasTextBlock

        first = CanvasTextBlock(
            object_id="unmanaged-projection-source",
            workspace_id="mindmap_projection",
            text="Must not become a graph node",
            position_x=0,
            position_y=0,
        )
        second = CanvasTextBlock(
            object_id="unmanaged-projection-target",
            workspace_id="mindmap_projection",
            text="Must not become a graph node either",
            position_x=100,
            position_y=0,
        )
        connector = CanvasConnector(
            connector_id="unmanaged-projection-link",
            workspace_id="mindmap_projection",
            source_object_id=first.object_id,
            target_object_id=second.object_id,
        )

        self.core.mind_map_workspace_sync.handle_canvas_event(
            {"event_type": "canvas_block_saved", "block": first}
        )
        self.core.mind_map_workspace_sync.handle_canvas_event(
            {"event_type": "canvas_connector_saved", "connector": connector}
        )

        self.assertIsNone(self.core.mind_map_module.find_source_node("canvas_block", first.object_id))
        self.assertIsNone(self.core.mind_map_module.find_source_node("canvas_block", second.object_id))
        self.assertFalse(
            any(
                link.source_reference and link.source_reference.source_id == connector.connector_id
                for link in self.core.mind_map_module.list_links()
            )
        )

    def test_import_reconciles_eligible_sources_with_provenance_and_link_evidence(self) -> None:
        export_path = self.project_root / "imported_mind_map.json"
        export_path.write_text(
            json.dumps({
                "graph_id": "imported",
                "nodes": [
                    {
                        "node_id": "source-node",
                        "title": "Imported Sheet",
                        "node_type": "sheet",
                        "source_reference": {
                            "source_type": "sheet",
                            "source_id": "sheet-42",
                            "source_locator": "chat-7",
                        },
                    },
                    {
                        "node_id": "target-node",
                        "title": "Imported Comment",
                        "node_type": "comment",
                        "source_reference": {
                            "source_type": "comment",
                            "source_id": "comment-9",
                            "source_locator": "chat-7/message-3",
                        },
                    },
                ],
                "links": [
                    {
                        "link_id": "imported-link",
                        "source_node_id": "source-node",
                        "target_node_id": "target-node",
                        "link_type": "supports",
                        "label": "import evidence",
                        "evidence": "Imported evidence is preserved.",
                    },
                ],
            }),
            encoding="utf-8",
        )

        imported = self.core.import_mind_map(export_path, replace_graph=True)
        source_node = next(node for node in imported.nodes if node.source_reference.source_id == "sheet-42")
        target_node = next(node for node in imported.nodes if node.source_reference.source_id == "comment-9")
        snapshot = self.core.canvas_module.get_snapshot_for_workspace("mindmap_projection")
        blocks = {block.metadata["mindmap_node_id"]: block for block in snapshot.text_blocks}
        connector = snapshot.connectors[0]

        self.assertEqual(
            {"source_type": "sheet", "source_id": "sheet-42", "source_locator": "chat-7"},
            {key: blocks[source_node.node_id].metadata[key] for key in ("source_type", "source_id", "source_locator")},
        )
        self.assertEqual(f"mindmap_projection_node_{source_node.node_id}", connector.source_object_id)
        self.assertEqual(f"mindmap_projection_node_{target_node.node_id}", connector.target_object_id)
        self.assertEqual("Imported evidence is preserved.", connector.comment)

    def test_startup_reconciliation_restores_projection_from_existing_graph(self) -> None:
        chat = self.core.create_chat(title="Restarted Projection")
        node = self.core.mind_map_module.find_source_node("chat", chat.chat_id)
        self.core.canvas_module._replace_mindmap_projection(
            "mindmap_projection", blocks=(), connectors=()
        )

        restarted = AmadeusCore(llm_client=object(), project_root=self.project_root)
        snapshot = restarted.canvas_module.get_snapshot_for_workspace("mindmap_projection")

        self.assertIn(
            node.node_id,
            {block.metadata["mindmap_node_id"] for block in snapshot.text_blocks},
        )


if __name__ == "__main__":
    unittest.main()
