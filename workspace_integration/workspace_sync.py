"""Synchronize real AMADEUS workspace objects with Mind Map source nodes.

The graph remains the relationship authority, while Chats, Sheets, Comments,
and Memory remain the authorities for their own content. This bridge translates
between those public module APIs without letting the GUI touch their storage.
"""

from __future__ import annotations

from typing import Any

from canvas_module.models import CanvasConnector, CanvasTextBlock
from mindmap.models import GraphLink, GraphNode, SourceReference


_WORKSPACE_TYPES = frozenset({"chat", "sheet", "comment", "memory"})
_CANVAS_BLOCK_SOURCE_TYPE = "canvas_block"
_CANVAS_CONNECTOR_SOURCE_TYPE = "canvas_connector"
_PROJECTION_WORKSPACE_ID = "mindmap_projection"
_PROJECTION_WORKSPACE_TITLE = "Mind Map"
_PROJECTION_SOURCE_TYPES = frozenset({"chat", "sheet", "memory", "comment", _CANVAS_BLOCK_SOURCE_TYPE})


class MindMapWorkspaceSync:
    """Create, refresh, and retrieve source-backed graph workspace objects."""

    def __init__(
        self,
        *,
        mind_map_module: Any,
        chat_history_store: Any,
        sheet_service: Any,
        comment_service: Any,
        memory_service: Any,
        canvas_module: Any,
    ) -> None:
        self.mind_map = mind_map_module
        self.chats = chat_history_store
        self.sheets = sheet_service
        self.comments = comment_service
        self.memory = memory_service
        self.canvas = canvas_module

    @property
    def workspace_types(self) -> frozenset[str]:
        return _WORKSPACE_TYPES

    def reconcile_canvas_projection(self) -> None:
        """Mirror eligible graph records into the dedicated read-only Canvas workspace."""

        workspace = self.canvas.ensure_workspace(_PROJECTION_WORKSPACE_ID, _PROJECTION_WORKSPACE_TITLE)
        snapshot = self.mind_map.get_snapshot()
        nodes = {
            node.node_id: node
            for node in snapshot.nodes
            if node.source_reference is not None
            and node.source_reference.source_type in _PROJECTION_SOURCE_TYPES
        }
        blocks = tuple(
            CanvasTextBlock(
                object_id=f"mindmap_projection_node_{node.node_id}",
                workspace_id=workspace.workspace_id,
                text=node.content or node.description or node.title,
                position_x=node.position_x,
                position_y=node.position_y,
                title=node.title,
                comment=node.description,
                created_by="amadeus",
                locked=True,
                metadata={
                    "mindmap_projection": True,
                    "mindmap_node_id": node.node_id,
                    "source_type": node.source_reference.source_type,
                    "source_id": node.source_reference.source_id,
                    "source_locator": node.source_reference.source_locator,
                },
            )
            for node in nodes.values()
        )
        block_ids = {node_id: f"mindmap_projection_node_{node_id}" for node_id in nodes}
        connectors = tuple(
            CanvasConnector(
                connector_id=f"mindmap_projection_link_{link.link_id}",
                workspace_id=workspace.workspace_id,
                source_object_id=block_ids[link.source_node_id],
                target_object_id=block_ids[link.target_node_id],
                relation_type=link.link_type,
                label=link.label,
                comment=link.evidence,
                created_by="amadeus",
                metadata={"mindmap_projection": True, "mindmap_link_id": link.link_id},
            )
            for link in snapshot.links
            if link.source_node_id in block_ids and link.target_node_id in block_ids
        )
        self.canvas.replace_mindmap_projection(
            workspace.workspace_id, blocks=blocks, connectors=connectors
        )

    def sync_existing_chats(self) -> list[GraphNode]:
        """Ensure every currently known dedicated chat has one source node."""
        return [self.sync_chat(chat) for chat in self.chats.list_chats()]

    def sync_chat(self, chat: Any) -> GraphNode:
        analysis = getattr(chat, "inner_brain_analysis", None)
        priority = str(getattr(chat, "priority", "Normal"))
        metadata = {
            "chat_priority": priority,
            "chat_purpose": str(getattr(chat, "purpose", "General")),
            "chat_scope": str(getattr(chat, "scope", "Local")),
            "tags": ["chat", str(getattr(chat, "purpose", "General")).lower().replace(" ", "_")],
            "source_registry": "chat_registry",
            "workspace_backed": True,
            "inner_brain_short_bullets": list(getattr(analysis, "short_bullets", ())),
            "inner_brain_detailed_summary": str(getattr(analysis, "detailed_summary", "")),
            "inner_brain_export_id": str(getattr(analysis, "export_id", "")),
        }
        node = self.mind_map.upsert_source_node(
            source_type="chat",
            source_id=str(chat.chat_id),
            title=str(chat.title),
            description=str(getattr(chat, "description", "")),
            content=str(getattr(analysis, "detailed_summary", "") or getattr(chat, "summary", "")),
            node_type="chat",
            importance=self._priority_score(priority),
            confidence=1.0,
            metadata=metadata,
        )
        self.reconcile_canvas_projection()
        return node

    def sync_sheet(self, sheet: Any) -> GraphNode:
        node = self.mind_map.upsert_source_node(
            source_type="sheet",
            source_id=str(sheet.sheet_id),
            title=str(sheet.title),
            description=str(getattr(sheet, "description", "")),
            content=str(getattr(sheet, "content", "")),
            node_type="sheet",
            source_locator=str(getattr(sheet, "chat_id", None) or ""),
            importance=0.62,
            confidence=1.0,
            metadata={
                "sheet_scope": str(getattr(sheet, "scope", "chat")),
                "chat_id": getattr(sheet, "chat_id", None),
                "workspace_backed": True,
                "tags": ["sheet"],
            },
        )
        chat_id = getattr(sheet, "chat_id", None)
        if chat_id:
            self._ensure_chat_relationship(str(chat_id), node.node_id, "contains")
        self.reconcile_canvas_projection()
        return node

    def sync_comment(self, comment: Any) -> GraphNode:
        selected_text = str(getattr(comment, "selected_text", ""))
        node = self.mind_map.upsert_source_node(
            source_type="comment",
            source_id=str(comment.comment_id),
            title=self._comment_title(comment),
            description=selected_text,
            content=str(comment.comment),
            node_type="comment",
            source_locator=str(getattr(comment, "chat_id", None) or ""),
            importance=0.52,
            confidence=1.0,
            metadata={
                "chat_id": getattr(comment, "chat_id", None),
                "comment_scope": str(getattr(comment, "scope", "chat")),
                "message_number": getattr(comment, "message_number", None),
                "comment_type": str(getattr(comment, "comment_type", "general")),
                "workspace_backed": True,
                "tags": ["comment"],
            },
        )
        chat_id = getattr(comment, "chat_id", None)
        if chat_id:
            self._ensure_chat_relationship(str(chat_id), node.node_id, "contains")
        self.reconcile_canvas_projection()
        return node

    def sync_memory(self, memory: Any) -> GraphNode:
        # Approved Creation bricks retain the same stable ID but expose structured scope names.
        chat_id = getattr(memory, "source_chat_id", getattr(memory, "scope_ref", None))
        scope = getattr(memory, "scope", getattr(memory, "scope_level", "global"))
        node = self.mind_map.upsert_source_node(
            source_type="memory",
            source_id=str(memory.memory_id),
            title=self._memory_title(str(memory.content)),
            description=f"{str(scope).title()} AMADEUS memory",
            content=str(memory.content),
            node_type="memory",
            source_locator=str(chat_id or ""),
            importance=0.72 if str(scope) == "global" else 0.62,
            confidence=1.0,
            metadata={
                "memory_scope": str(scope),
                "chat_id": chat_id,
                "workspace_backed": True,
                "tags": ["memory", str(scope)],
            },
        )
        if chat_id:
            self._ensure_chat_relationship(str(chat_id), node.node_id, "contains")
        self.reconcile_canvas_projection()
        return node

    def sync_canvas_block(self, block: Any) -> GraphNode:
        """Upsert one Canvas text block as its stable graph source node."""
        node = self.mind_map.upsert_source_node(
            source_type=_CANVAS_BLOCK_SOURCE_TYPE,
            source_id=str(block.object_id),
            title=str(block.title or block.text[:64]),
            description=str(block.comment),
            content=str(block.text),
            node_type="canvas",
            importance=0.5,
            confidence=1.0,
            metadata={
                "workspace_backed": True,
                "canvas_workspace_id": str(block.workspace_id),
                "canvas_created_by": str(block.created_by),
            },
        )
        position = (float(block.position_x), float(block.position_y))
        if (node.position_x, node.position_y) != position:
            node = self.mind_map.update_node(
                node.node_id,
                position_x=position[0],
                position_y=position[1],
            )
        self.reconcile_canvas_projection()
        return node

    def sync_canvas_connector(self, connector: Any) -> GraphLink | None:
        """Upsert a Canvas relationship after ensuring both endpoint nodes exist."""
        source = self.mind_map.find_source_node(
            _CANVAS_BLOCK_SOURCE_TYPE, str(connector.source_object_id)
        )
        target = self.mind_map.find_source_node(
            _CANVAS_BLOCK_SOURCE_TYPE, str(connector.target_object_id)
        )
        if source is None or target is None:
            blocks = {
                str(block.object_id): block
                for block in self.canvas.get_snapshot().text_blocks
            }
            if source is None and (block := blocks.get(str(connector.source_object_id))) is not None:
                source = self.sync_canvas_block(block)
            if target is None and (block := blocks.get(str(connector.target_object_id))) is not None:
                target = self.sync_canvas_block(block)
        if source is None or target is None:
            return None
        metadata = {
            "workspace_sync": True,
            "canvas_connector_type": str(connector.connector_type),
            "canvas_workspace_id": str(connector.workspace_id),
        }
        existing = self._find_source_link(_CANVAS_CONNECTOR_SOURCE_TYPE, str(connector.connector_id))
        fields = {
            "link_type": str(connector.relation_type),
            "label": str(connector.label),
            "evidence": str(connector.comment),
            "metadata": metadata,
        }
        if existing is not None:
            link = self.mind_map.update_link(existing.link_id, **fields)
        else:
            link = self.mind_map.create_link(
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            source_reference=SourceReference(_CANVAS_CONNECTOR_SOURCE_TYPE, str(connector.connector_id)),
            **fields,
            )
        self.reconcile_canvas_projection()
        return link

    def handle_canvas_event(self, event: dict[str, object]) -> None:
        """Project one persisted Canvas event without reaching into Canvas storage."""
        event_type = event.get("event_type")
        if self._is_projection_workspace_event(event):
            return
        if event_type == "canvas_block_saved":
            block = event.get("block")
            if block is not None and not self._is_managed_canvas_record(block):
                self.sync_canvas_block(block)
        elif event_type == "canvas_connector_saved":
            connector = event.get("connector")
            if connector is not None and not self._is_managed_canvas_record(connector):
                self.sync_canvas_connector(connector)
        elif event_type == "canvas_items_deleted":
            if event.get("mindmap_projection") is True:
                return
            for connector_id in event.get("deleted_connector_ids", ()):
                self._delete_source_link(_CANVAS_CONNECTOR_SOURCE_TYPE, str(connector_id))
            for object_id in event.get("deleted_object_ids", ()):
                self.delete_source_node(_CANVAS_BLOCK_SOURCE_TYPE, str(object_id))
        elif event_type == "canvas_snapshot_restored":
            snapshot = event.get("snapshot")
            if snapshot is not None:
                self._reconcile_canvas_snapshot(snapshot)

    def create_workspace_node(
        self,
        *,
        title: str,
        node_type: str,
        description: str = "",
        content: str = "",
        importance: float = 0.5,
        confidence: float = 1.0,
        position_x: float = 0.0,
        position_y: float = 0.0,
        position_locked: bool = False,
        create_workspace_object: bool = True,
        linked_chat_node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **extra: Any,
    ) -> GraphNode:
        """Create a graph-only node or a real source-backed workspace object."""
        clean_type = str(node_type or "idea").strip().lower()
        common = dict(
            title=title,
            node_type=clean_type,
            description=description,
            content=content,
            importance=importance,
            confidence=confidence,
            position_x=position_x,
            position_y=position_y,
            position_locked=position_locked,
            metadata=dict(metadata or {}),
            **extra,
        )
        if not create_workspace_object or clean_type not in _WORKSPACE_TYPES:
            if clean_type in _WORKSPACE_TYPES and not create_workspace_object:
                common["metadata"] = {
                    **common["metadata"],
                    "workspace_creation_disabled": True,
                }
            return self.mind_map.create_node(**common)

        if clean_type == "chat":
            chat = self.chats.create_chat(title=title, description=description)
            node = self.sync_chat(chat)
            return self._place_node(node, position_x, position_y, position_locked)

        chat_id = self._resolve_chat_id(linked_chat_node_id) or self.chats.get_current_chat_id()
        chat_node = self._ensure_chat_node(chat_id)
        text = str(content or description or title).strip()
        if clean_type == "sheet":
            source = self.sheets.create_sheet(
                title=title,
                description=description,
                content=content,
                scope="chat",
                chat_id=chat_id,
            )
            node = self.sync_sheet(source)
        elif clean_type == "comment":
            source = self.comments.add_comment(chat_id=chat_id, comment=text)
            node = self.sync_comment(source)
        else:
            source = self.memory.save_chat_memory(chat_id, text)
            node = self.sync_memory(source)
        self._ensure_link(chat_node.node_id, node.node_id, "contains", inject_into_chat=True)
        return self._place_node(node, position_x, position_y, position_locked)

    def materialize_linked_node(self, link: GraphLink) -> GraphNode | None:
        """Turn a manual workspace-typed node into a real object when linked to chat."""
        source = self.mind_map.get_node(link.source_node_id)
        target = self.mind_map.get_node(link.target_node_id)
        if source is None or target is None:
            return None
        pair = self._chat_and_other(source, target)
        if pair is None:
            return None
        chat_node, other = pair
        chat_id = chat_node.source_reference.source_id  # type: ignore[union-attr]
        self._ensure_link_metadata(link)
        if (
            other.source_reference is not None
            or other.node_type not in _WORKSPACE_TYPES
            or other.metadata.get("workspace_creation_disabled", False)
        ):
            return other

        text = str(other.content or other.description or other.title).strip()
        if other.node_type == "chat":
            chat = self.chats.create_chat(title=other.title, description=other.description)
            reference = SourceReference("chat", chat.chat_id)
        elif other.node_type == "sheet":
            sheet = self.sheets.create_sheet(
                title=other.title,
                description=other.description,
                content=other.content,
                scope="chat",
                chat_id=chat_id,
            )
            reference = SourceReference("sheet", sheet.sheet_id)
        elif other.node_type == "comment":
            comment = self.comments.add_comment(chat_id=chat_id, comment=text)
            reference = SourceReference("comment", comment.comment_id)
        else:
            memory = self.memory.save_chat_memory(chat_id, text)
            reference = SourceReference("memory", memory.memory_id)

        metadata = dict(other.metadata)
        metadata.update({"workspace_backed": True, "chat_id": chat_id})
        return self.mind_map.update_node(other.node_id, source_reference=reference, metadata=metadata)

    def update_workspace_source_from_node(self, node: GraphNode, changes: dict[str, Any]) -> None:
        """Propagate content edits from a source-backed graph node to its owner."""
        reference = node.source_reference
        if reference is None or not any(key in changes for key in ("title", "description", "content")):
            return
        title = str(changes.get("title", node.title))
        description = str(changes.get("description", node.description))
        content = str(changes.get("content", node.content))
        if reference.source_type == "chat":
            self.chats.update_chat_metadata(reference.source_id, title=title, description=description, summary=content)
        elif reference.source_type == "sheet":
            self.sheets.update_sheet(reference.source_id, title=title, description=description, content=content)
        elif reference.source_type == "comment":
            self.comments.update_comment(reference.source_id, content or description or title)
        elif reference.source_type == "memory":
            self.memory.update_memory(reference.source_id, content or description or title)

    def build_linked_context(self, chat_id: str, *, limit: int = 16, max_characters: int = 7000) -> str | None:
        """Format direct graph neighbors as literal, source-grounded chat data.

        Local models were previously given one ambiguous ``Context`` field. That
        made it easy to invent labels or reinterpret a sheet as generic memory.
        Each field is now explicit, delimited, and described as literal data.
        """
        chat_node = self.mind_map.find_source_node("chat", chat_id)
        if chat_node is None:
            return None
        neighborhood = self.mind_map.get_neighborhood(chat_node.node_id, depth=1)
        nodes = {node.node_id: node for node in neighborhood.nodes}
        records: list[str] = []
        for link in neighborhood.links:
            if link.source_node_id == chat_node.node_id:
                other_id, direction = link.target_node_id, "outgoing"
            elif link.target_node_id == chat_node.node_id:
                other_id, direction = link.source_node_id, "incoming"
            else:
                continue
            if link.metadata.get("inject_into_chat", True) is False:
                continue
            other = nodes.get(other_id)
            if other is None or other.status == "source_missing":
                continue
            description = str(other.description or "").strip()
            content = str(other.content or "").strip()
            if len(description) > 600:
                description = description[:597].rstrip() + "..."
            if len(content) > 1400:
                content = content[:1397].rstrip() + "..."
            relation = link.label or link.link_type.replace("_", " ")
            source_type = other.source_reference.source_type if other.source_reference else "graph_only"
            source_id = other.source_reference.source_id if other.source_reference else "none"
            records.append(
                "\n".join((
                    "--- LINKED OBJECT ---",
                    f"Graph node ID: {other.node_id}",
                    f"Title (literal): {other.title}",
                    f"Node type (literal): {other.node_type}",
                    f"Source type: {source_type}",
                    f"Source ID: {source_id}",
                    f"Relationship direction: {direction}",
                    f"Relationship type (literal): {relation}",
                    f"Description (literal): {description or '<empty>'}",
                    "Content (literal, between markers):",
                    "<<<CONTENT",
                    content or "<empty>",
                    "CONTENT",
                    "--- END LINKED OBJECT ---",
                ))
            )
            if len(records) >= limit:
                break
        if not records:
            return None
        result = (
            "[EXACT LINKED MIND MAP WORKSPACE DATA]\n"
            "The records below are literal AMADEUS workspace/graph fields, not generated summaries.\n"
            "Grounding rules:\n"
            "- Use only titles, types, relationships, descriptions, content, and IDs explicitly written below.\n"
            "- Never invent labels, node numbers, categories, stakeholders, timelines, or hidden meanings.\n"
            "- Do not call an object memory unless its literal node/source type is memory.\n"
            "- When asked what is written in a sheet/comment/node, report its literal Description and Content fields.\n"
            "- If a field says <empty>, state that it is empty instead of filling it in.\n"
            "- These exact records override older assistant claims about the same linked objects.\n"
            + "\n\n".join(records)
        )
        return result if len(result) <= max_characters else result[:max_characters] + "\n[Linked context truncated.]"

    def delete_workspace_source_for_node(self, node: GraphNode) -> GraphNode | None:
        """Delete the real object represented by one source-backed graph node.

        The Mind Map GUI calls this through Core before deleting the graph node.
        Graph-only nodes have no external owner and therefore need no action.
        A deleted last chat creates a fresh Main Chat through ChatHistoryStore;
        that replacement chat is projected back into the graph and returned.
        """
        reference = node.source_reference
        if reference is None:
            return None

        try:
            if reference.source_type == "chat":
                active_chat = self.chats.delete_chat(reference.source_id)
                return self.sync_chat(active_chat)
            if reference.source_type == "sheet":
                self.sheets.delete_sheet(reference.source_id)
            elif reference.source_type == "comment":
                self.comments.delete_comment(reference.source_id)
            elif reference.source_type == "memory":
                self.memory.delete_memory(reference.source_id)
            elif reference.source_type == _CANVAS_BLOCK_SOURCE_TYPE:
                workspace_id = str(node.metadata.get("canvas_workspace_id", "")).strip()
                if not workspace_id:
                    return None
                self.canvas.delete_items_in_workspace(
                    workspace_id,
                    object_ids=[reference.source_id],
                )
        except (KeyError, ValueError):
            # The graph may retain a source reference after an object was removed
            # elsewhere. Deleting that stale graph node should still succeed.
            return None
        return None

    def delete_workspace_source_for_link(self, link: GraphLink) -> None:
        """Delete the Canvas connector represented by one source-backed graph link."""
        reference = link.source_reference
        if reference is None or reference.source_type != _CANVAS_CONNECTOR_SOURCE_TYPE:
            return
        workspace_id = str(link.metadata.get("canvas_workspace_id", "")).strip()
        if not workspace_id:
            return
        try:
            self.canvas.delete_items_in_workspace(
                workspace_id,
                connector_ids=[reference.source_id],
            )
        except KeyError:
            # A Canvas event may have already removed the connector and its link.
            return

    def build_panel_payload(self, chat_id: str) -> dict[str, Any]:
        """Return GUI-safe rows for the active chat's automatic graph context."""
        chat_node = self.mind_map.find_source_node("chat", chat_id)
        rows: list[dict[str, Any]] = []
        if chat_node is not None:
            neighborhood = self.mind_map.get_neighborhood(chat_node.node_id, depth=1)
            nodes = {node.node_id: node for node in neighborhood.nodes}
            for link in neighborhood.links:
                if link.source_node_id == chat_node.node_id:
                    other_id, direction = link.target_node_id, "outgoing"
                elif link.target_node_id == chat_node.node_id:
                    other_id, direction = link.source_node_id, "incoming"
                else:
                    continue
                other = nodes.get(other_id)
                if other is None:
                    continue
                rows.append({
                    "node_id": other.node_id,
                    "title": other.title,
                    "node_type": other.node_type,
                    "description": other.description,
                    "content": other.content,
                    "relationship": link.label or link.link_type.replace("_", " "),
                    "direction": direction,
                    "inject_into_chat": link.metadata.get("inject_into_chat", True) is not False,
                    "source_type": other.source_reference.source_type if other.source_reference else "",
                    "source_id": other.source_reference.source_id if other.source_reference else "",
                })
        lines = []
        for row in rows:
            state = "active" if row["inject_into_chat"] else "not injected"
            lines.append(f"{row['title']} [{row['node_type']}] · {row['relationship']} · {state}")
            body = str(row["content"] or row["description"]).strip()
            if body:
                lines.append(body[:500])
            lines.append("")
        return {
            "type": "mindmap_links",
            "title": "Linked Mind Map Context",
            "content": "\n".join(lines).strip() or "No Mind Map nodes are linked to this chat yet.",
            "metadata": {"chat_id": chat_id, "rows": rows, "count": len(rows)},
        }

    def delete_source_node(self, source_type: str, source_id: str) -> None:
        node = self.mind_map.find_source_node(source_type, source_id)
        if node is not None:
            self.mind_map.delete_node(node.node_id)
            self.reconcile_canvas_projection()

    def _reconcile_canvas_snapshot(self, snapshot: Any) -> None:
        """Make the graph match the restored active Canvas workspace snapshot."""
        if str(getattr(snapshot, "workspace_id", "")) == _PROJECTION_WORKSPACE_ID:
            return
        blocks = tuple(block for block in snapshot.text_blocks if not self._is_managed_canvas_record(block))
        connectors = tuple(
            connector for connector in snapshot.connectors if not self._is_managed_canvas_record(connector)
        )
        for block in blocks:
            self.sync_canvas_block(block)
        for connector in connectors:
            self.sync_canvas_connector(connector)

        workspace_id = str(snapshot.workspace_id)
        block_ids = {str(block.object_id) for block in blocks}
        connector_ids = {str(connector.connector_id) for connector in connectors}
        for link in self.mind_map.list_links():
            reference = link.source_reference
            if (
                reference is not None
                and reference.source_type == _CANVAS_CONNECTOR_SOURCE_TYPE
                and link.metadata.get("canvas_workspace_id", workspace_id) == workspace_id
                and reference.source_id not in connector_ids
            ):
                self.mind_map.delete_link(link.link_id)
        for node in self.mind_map.list_nodes():
            reference = node.source_reference
            if (
                reference is not None
                and reference.source_type == _CANVAS_BLOCK_SOURCE_TYPE
                and node.metadata.get("canvas_workspace_id") == workspace_id
                and reference.source_id not in block_ids
            ):
                self.mind_map.delete_node(node.node_id)

    def _find_source_link(self, source_type: str, source_id: str) -> GraphLink | None:
        return next(
            (
                link
                for link in self.mind_map.list_links()
                if link.source_reference is not None
                and link.source_reference.source_type == source_type
                and link.source_reference.source_id == source_id
            ),
            None,
        )

    @staticmethod
    def _is_managed_canvas_record(record: object) -> bool:
        """Exclude Mind Map-owned Canvas projections from the reverse bridge."""

        metadata = getattr(record, "metadata", {})
        return isinstance(metadata, dict) and metadata.get("mindmap_projection") is True

    @staticmethod
    def _is_projection_workspace_event(event: dict[str, object]) -> bool:
        """Reject all Canvas-to-graph synchronization from the managed workspace."""

        for field in ("block", "connector", "snapshot"):
            record = event.get(field)
            if str(getattr(record, "workspace_id", "")) == _PROJECTION_WORKSPACE_ID:
                return True
        return False

    def _delete_source_link(self, source_type: str, source_id: str) -> None:
        link = self._find_source_link(source_type, source_id)
        if link is not None:
            self.mind_map.delete_link(link.link_id)

    def mark_chat_missing(self, chat_id: str) -> None:
        node = self.mind_map.find_source_node("chat", chat_id)
        if node is None:
            return
        metadata = dict(node.metadata)
        metadata["source_missing"] = True
        self.mind_map.update_node(node.node_id, status="source_missing", metadata=metadata)

    def _ensure_chat_node(self, chat_id: str) -> GraphNode:
        existing = self.mind_map.find_source_node("chat", chat_id)
        if existing is not None:
            return existing
        chat = self.chats.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Unknown chat id: {chat_id}")
        return self.sync_chat(chat)

    def _resolve_chat_id(self, chat_node_id: str | None) -> str | None:
        if not chat_node_id:
            return None
        node = self.mind_map.get_node(chat_node_id)
        if node and node.source_reference and node.source_reference.source_type == "chat":
            return node.source_reference.source_id
        return None

    def _ensure_chat_relationship(self, chat_id: str, node_id: str, link_type: str) -> GraphLink:
        chat_node = self._ensure_chat_node(chat_id)
        return self._ensure_link(chat_node.node_id, node_id, link_type, inject_into_chat=True)

    def _ensure_link(self, source_node_id: str, target_node_id: str, link_type: str, *, inject_into_chat: bool) -> GraphLink:
        for link in self.mind_map.list_links():
            if link.source_node_id == source_node_id and link.target_node_id == target_node_id:
                if "inject_into_chat" not in link.metadata:
                    metadata = dict(link.metadata)
                    metadata["inject_into_chat"] = inject_into_chat
                    return self.mind_map.update_link(link.link_id, metadata=metadata)
                return link
        return self.mind_map.create_link(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            link_type=link_type,
            strength=0.78,
            confidence=1.0,
            permanence=0.85,
            metadata={"inject_into_chat": inject_into_chat, "workspace_sync": True},
        )

    def _ensure_link_metadata(self, link: GraphLink) -> GraphLink:
        if "inject_into_chat" in link.metadata:
            return link
        metadata = dict(link.metadata)
        metadata["inject_into_chat"] = True
        return self.mind_map.update_link(link.link_id, metadata=metadata)

    @staticmethod
    def _chat_and_other(first: GraphNode, second: GraphNode) -> tuple[GraphNode, GraphNode] | None:
        if first.source_reference and first.source_reference.source_type == "chat":
            return first, second
        if second.source_reference and second.source_reference.source_type == "chat":
            return second, first
        return None

    def _place_node(self, node: GraphNode, x: float, y: float, locked: bool) -> GraphNode:
        return self.mind_map.update_node(
            node.node_id,
            position_x=float(x),
            position_y=float(y),
            position_locked=bool(locked),
        )

    @staticmethod
    def _priority_score(priority: str) -> float:
        return {"critical": 1.0, "important": 0.82, "normal": 0.55, "low": 0.32, "ignore": 0.10}.get(priority.lower(), 0.55)

    @staticmethod
    def _comment_title(comment: Any) -> str:
        number = getattr(comment, "message_number", None)
        return f"Comment on message {number}" if number is not None else f"Comment {comment.comment_id}"

    @staticmethod
    def _memory_title(content: str) -> str:
        clean = " ".join(content.split())
        return clean[:64] + ("..." if len(clean) > 64 else "") or "Memory"
