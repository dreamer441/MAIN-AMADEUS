"""Explicit application routes, with feature behavior owned by registered modules."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from amadeus_core.module_registry import ModuleRegistry
from amadeus_core.module_routes import CanvasRoutes, HabitRoutes


class CoreCoordinator:
    """Route GUI/public API calls; application setup and modules own implementation."""

    def __init__(self, llm_client: object | None = None, project_root: Path | None = None,
                 inner_brain_service: object | None = None, *, module_registry: ModuleRegistry | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        if module_registry is None:
            # The lazy startup boundary keeps Core importable without feature or Qt imports.
            from amadeus_app.composition import compose_application
            module_registry = compose_application(self.project_root, llm_client, inner_brain_service)
        self.module_registry = module_registry
        self.canvas = CanvasRoutes(module_registry)
        self.habits = HabitRoutes(module_registry)

    def get_canvas_workspace_descriptor(self) -> Any:
        """Return safe Canvas workspace metadata for the persistent GUI page."""
        return self.module_registry.require("canvas").get_workspace_descriptor()

    def register_creation_source(self, **fields: Any) -> Any:
        """Register caller-supplied source content without resolving its locator."""
        return self.module_registry.require("memory").register_knowledge_source(**fields)

    def generate_missing_creation_metadata(self, source_id: str) -> Any:
        """Generate only missing source metadata through the registered Creation facade."""
        return self.module_registry.require("creation").generate_missing_metadata(source_id)

    def refresh_creation_metadata(
        self,
        source_id: str,
        selected_layers: Any = None,
        *,
        replace_manual: bool = False,
    ) -> Any:
        """Refresh stale generated source metadata without replacing manual fields by default."""
        return self.module_registry.require('creation').refresh_generated_metadata(
            source_id,
            selected_layers,
            replace_manual=replace_manual,
        )

    def regenerate_selected_creation_metadata(
        self,
        source_id: str,
        layers: Any,
        *,
        replace_manual: bool = False,
    ) -> Any:
        """Explicitly regenerate selected metadata fields through the Creation facade."""
        return self.module_registry.require('creation').regenerate_selected_metadata(
            source_id,
            layers,
            replace_manual=replace_manual,
        )

    def categorize_creation_source(self, source_id: str, *, apply_changes: bool=True) -> Any:
        """Generate and optionally apply a typed categorization for one registered source."""
        return self.module_registry.require("creation").categorize_source(source_id, apply_changes=apply_changes)

    def propose_creation_memory_bricks(self, source_id: str) -> list[Any]:
        """Return non-persistent Memory Brick proposals for explicit review."""
        return self.module_registry.require("creation").propose_memory_bricks(source_id)

    def create_approved_creation_memory_bricks(
        self,
        source_id: str,
        proposals: list[Any],
        approved_ids: set[str],
    ) -> Any:
        """Persist only proposal IDs explicitly approved by the caller."""
        return self.module_registry.require('creation').create_approved_memory_bricks(
            source_id,
            proposals,
            approved_ids,
        )

    def create_creation_workspace_object(
        self,
        kind: str,
        request: str,
        *,
        chat_id: str | None = None,
        scope: str = 'global',
    ) -> Any:
        """Create an approved workspace object with the scope fixed before approval."""
        return self.module_registry.require('creation').create_workspace_object(
            kind,
            request,
            chat_id=chat_id,
            scope=scope,
        )

    def create_pending_creation_action(self, request: Any, *, route: str) -> Any:
        """Convert a typed annotation or advisory intent into one non-persistent action."""
        return self.module_registry.require('creation_requests').create_pending_creation_action(
            request,
            route=route,
        )

    def create_pending_action(
        self,
        *,
        kind: str,
        fields: dict[str, Any],
        scope: str = 'global',
        linked_chat_id: str = '',
    ) -> Any:
        """Prepare a registered owner action without writing owner storage."""
        return self.module_registry.require('permissions').create_pending_action(
            kind=kind,
            fields=fields,
            scope=scope,
            linked_chat_id=linked_chat_id,
        )

    def approve_pending_action(self, action_id: str) -> Any:
        """Consume one verified request and route it through existing Core facades."""
        return self.module_registry.require("permissions").approve_pending_action(action_id)

    def decline_pending_action(self, action_id: str) -> None:
        """Discard one pending request without calling an owner service."""
        return self.module_registry.require("permissions").decline_pending_action(action_id)

    def get_flow_annotation_suggestions(self, text: str) -> list[dict[str, str]]:
        """Return the same annotation suggestions used by dedicated chat."""
        return self.module_registry.require("annotation_suggestions").get_flow_annotation_suggestions(text)

    def handle_user_message(
        self,
        message: str,
        callable_context: str | None = None,
        event_listener: Callable[[dict[str, object]], None] | None = None,
        response_mode_override: Any | str | None = None,
    ) -> dict[str, Any]:
        """Route user text and return both AMADEUS output and Process Monitor trace."""
        return self.module_registry.require('chat_workspace').handle_user_message(
            message,
            callable_context,
            event_listener,
            response_mode_override,
        )

    def handle_flow_message(
        self,
        message: str,
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Handle the isolated Flow home conversation without changing normal chat routing."""
        return self.module_registry.require("flow_requests").handle_flow_message(message, event_listener)

    def handle_canvas_message(
        self,
        *,
        instruction: str = '',
        context_mode: str = 'viewport',
        visible_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_connector_ids: list[str] | tuple[str, ...] | set[str] = (),
        branch_root_id: str | None = None,
        model_weight: str = 'normal',
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Route one structured Canvas request and return committed scene objects."""
        return self.module_registry.require('canvas_requests').handle_canvas_message(
            instruction=instruction,
            context_mode=context_mode,
            visible_object_ids=visible_object_ids,
            selected_object_ids=selected_object_ids,
            selected_connector_ids=selected_connector_ids,
            branch_root_id=branch_root_id,
            model_weight=model_weight,
            event_listener=event_listener,
        )

    def load_flow_history(self) -> list[Any]:
        """Return persisted Flow messages for the GUI without exposing Flow storage."""
        return self.module_registry.require("flow_requests").load_flow_history()

    def subscribe_mind_map(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Subscribe a GUI or adapter to completed graph changes through Core."""
        return self.module_registry.require("graph_workspace").subscribe_mind_map(listener)

    def get_mind_map_snapshot(self) -> Any:
        """Return the active graph snapshot for a Core-mediated view refresh."""
        return self.module_registry.require("graph_workspace").get_mind_map_snapshot()

    def create_mind_map_node(self, **fields: Any) -> Any:
        """Create one validated graph-only node through the Mind Map module."""
        return self.module_registry.require("graph_workspace").create_mind_map_node(**fields)

    def create_mind_map_workspace_node(self, **fields: Any) -> Any:
        """Create a node and, for supported types, its real AMADEUS object."""
        return self.module_registry.require("graph_workspace").create_mind_map_workspace_node(**fields)

    def update_mind_map_node(self, node_id: str, **changes: Any) -> Any:
        """Update one graph node and mirror content edits to its source object."""
        return self.module_registry.require("graph_workspace").update_mind_map_node(node_id, **changes)

    def move_mind_map_node(self, node_id: str, position_x: float, position_y: float, **fields: Any) -> Any:
        """Persist a graph node position without exposing graph storage to the GUI."""
        return self.module_registry.require('graph_workspace').move_mind_map_node(
            node_id,
            position_x,
            position_y,
            **fields,
        )

    def move_mind_map_nodes(self, positions: dict[str, tuple[float, float]]) -> None:
        """Persist a complete layout projection in one graph transaction."""
        return self.module_registry.require("graph_workspace").move_mind_map_nodes(positions)

    def delete_mind_map_node(self, node_id: str, delete_source: bool=True, **fields: Any) -> None:
        """Delete one graph node and, by default, its real workspace object."""
        return self.module_registry.require('graph_workspace').delete_mind_map_node(
            node_id,
            delete_source,
            **fields,
        )

    def create_mind_map_link(self, **fields: Any) -> Any:
        """Create a relationship and materialize workspace-typed chat neighbors."""
        return self.module_registry.require("graph_workspace").create_mind_map_link(**fields)

    def update_mind_map_link(self, link_id: str, **changes: Any) -> Any:
        """Update one graph relationship through the Mind Map module."""
        return self.module_registry.require("graph_workspace").update_mind_map_link(link_id, **changes)

    def delete_mind_map_link(self, link_id: str, **fields: Any) -> None:
        """Delete one graph relationship and its Canvas source when applicable."""
        return self.module_registry.require("graph_workspace").delete_mind_map_link(link_id, **fields)

    def search_mind_map_nodes(self, query: str, limit: int=50) -> list[Any]:
        """Search graph nodes through the module's validated retrieval API."""
        return self.module_registry.require("graph_workspace").search_mind_map_nodes(query, limit)

    def get_mind_map_neighborhood(self, root_node_id: str, depth: int=1) -> Any:
        """Return a bounded graph neighborhood through the Mind Map module."""
        return self.module_registry.require("graph_workspace").get_mind_map_neighborhood(root_node_id, depth)

    def build_mind_map_context(self, query: str='', *, limit: int=8, depth: int=1, max_nodes: int=28) -> Any:
        """Return bounded node-and-link context without exposing graph storage."""
        return self.module_registry.require('graph_workspace').build_mind_map_context(
            query,
            limit=limit,
            depth=depth,
            max_nodes=max_nodes,
        )

    def upsert_mind_map_source_node(self, **fields: Any) -> Any:
        """Create or refresh a graph node for a future AMADEUS source adapter."""
        return self.module_registry.require("graph_workspace").upsert_mind_map_source_node(**fields)

    def export_mind_map(self, destination: Path | str) -> Path:
        """Export the active graph as portable JSON through the Mind Map module."""
        return self.module_registry.require("graph_workspace").export_mind_map(destination)

    def import_mind_map(self, source: Path | str, *, replace_graph: bool=False) -> Any:
        """Import portable graph JSON through the Mind Map module."""
        return self.module_registry.require("graph_workspace").import_mind_map(source, replace_graph=replace_graph)

    def handle_side_ask(self, question: str, selected_text: str='') -> dict[str, Any]:
        """Answer a Side Ask question without saving it to visible chat history."""
        return self.module_registry.require("side_ask_workflow").handle_side_ask(question, selected_text)

    def get_project_tree(self, relative_path: str='') -> dict[str, Any]:
        """Return a verified direct project-root tree listing for the Code Viewer."""
        return self.module_registry.require("project_workspace").get_project_tree(relative_path)

    def open_project_file(self, relative_path: str) -> dict[str, Any]:
        """Open one verified project file through the trusted reader only."""
        return self.module_registry.require("project_workspace").open_project_file(relative_path)

    def ask_about_project_file(
        self,
        relative_path: str,
        question: str,
        include_context: bool = False,
        line_range: str = '',
    ) -> dict[str, Any]:
        """Ask a direct question, adding verified selected-file context only when enabled."""
        return self.module_registry.require('project_workspace').ask_about_project_file(
            relative_path,
            question,
            include_context,
            line_range,
        )

    def save_side_ask_to_chat(self, question: str, answer: str, selected_text: str='') -> list[Any]:
        """Persist the latest Side Ask Q&A into the active chat and return new messages."""
        return self.module_registry.require('side_ask_workflow').save_side_ask_to_chat(
            question,
            answer,
            selected_text,
        )

    def add_comment(self, comment: str, selected_text: str='') -> Any:
        """Save a comment and project it into the active chat's Mind Map."""
        return self.module_registry.require("workspace_documents").add_comment(comment, selected_text)

    def update_comment(self, comment_id: str, comment: str) -> Any:
        """Update one comment and its source-backed Mind Map node."""
        return self.module_registry.require("workspace_documents").update_comment(comment_id, comment)

    def delete_comment(self, comment_id: str) -> None:
        """Delete one comment and its exact source-backed graph node."""
        return self.module_registry.require("workspace_documents").delete_comment(comment_id)

    def get_comments_panel_payload(self) -> dict[str, Any]:
        """Return comments for the current chat as a right-panel payload."""
        return self.module_registry.require("workspace_documents").get_comments_panel_payload()

    def get_linked_mind_map_panel_payload(self) -> dict[str, Any]:
        """Return direct Mind Map neighbors active for the current chat."""
        return self.module_registry.require("workspace_documents").get_linked_mind_map_panel_payload()

    def get_annotation_suggestions(self, current_input: str) -> list[dict[str, str]]:
        """Return GUI suggestions for slash/annotation building."""
        return self.module_registry.require("annotation_suggestions").get_annotation_suggestions(current_input)

    def list_chats(self) -> list[Any]:
        """Return known chats for the GUI selector."""
        return self.module_registry.require("chat_lifecycle").list_chats()

    def get_current_chat_id(self) -> str:
        """Return the currently active chat id for GUI selection state."""
        return self.module_registry.require("chat_lifecycle").get_current_chat_id()

    def get_current_chat_metadata(self) -> Any:
        """Return metadata for the active chat workspace."""
        return self.module_registry.require("chat_lifecycle").get_current_chat_metadata()

    def refresh_chat_inner_brain(self, chat_id: str | None=None) -> Any:
        """Explicitly generate and persist the active chat's five analysis layers."""
        return self.module_registry.require("chat_metadata").refresh_chat_inner_brain(chat_id)

    def create_chat_inner_brain_export(self, chat_id: str | None=None) -> Any:
        """Create an export only from the explicit Chat Data action."""
        return self.module_registry.require("chat_metadata").create_chat_inner_brain_export(chat_id)

    def get_chat_data_panel_payload(self, suggested_write_actions: tuple[str, ...]=()) -> dict[str, Any]:
        """Return display-only Chat Data state for the active chat side-panel tab."""
        return self.module_registry.require("chat_metadata").get_chat_data_panel_payload(suggested_write_actions)

    def create_chat(
        self,
        title: str | None = None,
        description: str | None = None,
        priority: Any = 'Normal',
        purpose: Any = 'General',
        scope: Any = 'Local',
        response_mode: Any | str = 'normal',
    ) -> Any:
        """Create a new chat, make it active, and create its Mind Map node."""
        return self.module_registry.require('chat_lifecycle').create_chat(
            title,
            description,
            priority,
            purpose,
            scope,
            response_mode,
        )

    def update_chat_metadata(
        self,
        chat_id: str,
        title: str | None = None,
        description: str | None = None,
        summary: str | None = None,
        priority: Any | None = None,
        purpose: Any | None = None,
        scope: Any | None = None,
        response_mode: Any | str | None = None,
    ) -> Any:
        """Update chat metadata and refresh its source-backed graph node."""
        return self.module_registry.require('chat_lifecycle').update_chat_metadata(
            chat_id,
            title,
            description,
            summary,
            priority,
            purpose,
            scope,
            response_mode,
        )

    def delete_chat(self, chat_id: str | None=None) -> Any:
        """Delete a chat, preserve its graph record as missing, and sync the active chat."""
        return self.module_registry.require("chat_lifecycle").delete_chat(chat_id)

    def switch_chat(self, chat_id: str) -> Any:
        """Switch active chat for future saves and context building."""
        return self.module_registry.require("chat_lifecycle").switch_chat(chat_id)

    def load_chat_history(self, chat_id: str | None=None) -> list[Any]:
        """Load persisted messages for the selected or active chat."""
        return self.module_registry.require("chat_lifecycle").load_chat_history(chat_id)

    def list_sheets(self, scope: str='all') -> list[Any]:
        """Return sheets visible from the current chat for GUI selectors."""
        return self.module_registry.require("workspace_documents").list_sheets(scope)

    def create_sheet(self, title: str, description: str='', content: str='', scope: str='chat') -> Any:
        """Create a sheet and project chat-scoped sheets into the Mind Map."""
        return self.module_registry.require("workspace_documents").create_sheet(title, description, content, scope)

    def update_sheet(
        self,
        sheet_id: str,
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        scope: str | None = None,
    ) -> Any:
        """Update a sheet and refresh its source-backed Mind Map node."""
        return self.module_registry.require('workspace_documents').update_sheet(
            sheet_id,
            title,
            description,
            content,
            scope,
        )

    def delete_sheet(self, sheet_id: str) -> None:
        """Delete one sheet and its exact source-backed graph node."""
        return self.module_registry.require("workspace_documents").delete_sheet(sheet_id)

    def get_sheets_panel_payload(self, scope: str='all', selected_sheet_id: str | None=None) -> dict[str, Any]:
        """Return a side-panel payload for the current chat's visible sheets."""
        return self.module_registry.require('workspace_documents').get_sheets_panel_payload(
            scope,
            selected_sheet_id,
        )

    def get_materials_panel_payload(self) -> dict[str, Any]:
        """Return material rows without opening or injecting a selected reference."""
        return self.module_registry.require("materials_workspace").get_materials_panel_payload()

    def list_materials(self) -> list[dict[str, Any]]:
        """Return material metadata for non-GUI callers through Materials only."""
        return self.module_registry.require("materials_workspace").list_materials()

    def preview_material(self, material_id: str) -> dict[str, Any]:
        """Preview one explicitly selected Materials record through its module API."""
        return self.module_registry.require("materials_workspace").preview_material(material_id)

    def open_material(self, material_id: str) -> dict[str, Any]:
        """Open one explicitly selected Materials record without injecting it."""
        return self.module_registry.require("materials_workspace").open_material(material_id)

    def get_material_reference(self, material_id: str) -> str:
        """Return a selected stable material reference for GUI clipboard actions."""
        return self.module_registry.require("materials_workspace").get_material_reference(material_id)

    def get_material_copy_text(self, material_id: str) -> str:
        """Return the selected material's Core-owned clipboard text."""
        return self.module_registry.require("materials_workspace").get_material_copy_text(material_id)

    def remove_material(self, material_id: str) -> None:
        """Remove one explicitly selected Materials record where supported."""
        return self.module_registry.require("materials_workspace").remove_material(material_id)

    def handle_material_message(
        self,
        material_id: str,
        message: str,
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Use one selected material as callable context for this one chat request."""
        return self.module_registry.require('materials_workspace').handle_material_message(
            material_id,
            message,
            event_listener,
        )

    # Compatibility accessors for existing integrations; GUI uses routed operations.
    @property
    def llm_client(self) -> Any:
        """Return the registered llm_client service for legacy integrations."""
        return self.module_registry.require("llm_client")

    @property
    def inner_brain_service(self) -> Any:
        """Return the registered inner_brain service for legacy integrations."""
        return self.module_registry.require("inner_brain")

    @property
    def file_reader(self) -> Any:
        """Return the registered file_reader service for legacy integrations."""
        return self.module_registry.require("file_reader")

    @property
    def identity_service(self) -> Any:
        """Return the registered identity service for legacy integrations."""
        return self.module_registry.require("identity")

    @property
    def identity_prompt_builder(self) -> Any:
        """Return the registered identity_prompts service for legacy integrations."""
        return self.module_registry.require("identity_prompts")

    @property
    def chat_history_store(self) -> Any:
        """Return the registered history service for legacy integrations."""
        return self.module_registry.require("history")

    @property
    def flow_chat_store(self) -> Any:
        """Return the registered flow_history service for legacy integrations."""
        return self.module_registry.require("flow_history")

    @property
    def chat_registry(self) -> Any:
        """Return the registered chat_registry service for legacy integrations."""
        return self.module_registry.require("chat_registry")

    @property
    def flow_context_builder(self) -> Any:
        """Return the registered flow_context_builder service for legacy integrations."""
        return self.module_registry.require("flow_context_builder")

    @property
    def memory_service(self) -> Any:
        """Return the registered memory service for legacy integrations."""
        return self.module_registry.require("memory")

    @property
    def sheet_service(self) -> Any:
        """Return the registered sheets service for legacy integrations."""
        return self.module_registry.require("sheets")

    @property
    def export_service(self) -> Any:
        """Return the registered exports service for legacy integrations."""
        return self.module_registry.require("exports")

    @property
    def materials_service(self) -> Any:
        """Return the registered materials service for legacy integrations."""
        return self.module_registry.require("materials")

    @property
    def side_ask_service(self) -> Any:
        """Return the registered side_ask service for legacy integrations."""
        return self.module_registry.require("side_ask")

    @property
    def comment_service(self) -> Any:
        """Return the registered comments service for legacy integrations."""
        return self.module_registry.require("comments")

    @property
    def canvas_module(self) -> Any:
        """Return the registered canvas service for legacy integrations."""
        return self.module_registry.require("canvas")

    @property
    def mind_map_module(self) -> Any:
        """Return the registered mind_map service for legacy integrations."""
        return self.module_registry.require("mind_map")

    @property
    def mind_map_workspace_sync(self) -> Any:
        """Return the registered workspace_sync service for legacy integrations."""
        return self.module_registry.require("workspace_sync")

    @property
    def creation_module(self) -> Any:
        """Return the registered creation service for legacy integrations."""
        return self.module_registry.require("creation")

    @property
    def context_builder(self) -> Any:
        """Return the registered context_builder service for legacy integrations."""
        return self.module_registry.require("context_builder")

    @property
    def annotation_parser(self) -> Any:
        """Return the registered annotation_parser service for legacy integrations."""
        return self.module_registry.require("annotation_parser")

    @property
    def annotation_registry(self) -> Any:
        """Return the registered annotations service for legacy integrations."""
        return self.module_registry.require("annotations")

    @property
    def annotation_context(self) -> Any:
        """Return the registered annotation_context service for legacy integrations."""
        return self.module_registry.require("annotation_context")

    @property
    def annotation_suggestion_service(self) -> Any:
        """Return the registered suggestion_service service for legacy integrations."""
        return self.module_registry.require("suggestion_service")

    @property
    def callable_context_router(self) -> Any:
        """Return the registered selected_context service for legacy integrations."""
        return self.module_registry.require("selected_context")

    @property
    def chat_metadata_resolver(self) -> Any:
        """Return the registered chat_metadata_resolver service for legacy integrations."""
        return self.module_registry.require("chat_metadata_resolver")

    @property
    def pending_actions(self) -> Any:
        """Return the registered pending_actions service for legacy integrations."""
        return self.module_registry.require("pending_actions")

    @property
    def habit_tracker_service(self) -> Any:
        """Return the registered habit_tracker service for legacy integrations."""
        return self.module_registry.require("habit_tracker")

    @property
    def flow_habit_requests(self) -> Any:
        """Return the registered flow_habit_requests service for legacy integrations."""
        return self.module_registry.require("flow_habit_requests")

    @property
    def flow_chat_service(self) -> Any:
        """Return the registered flow_chat service for legacy integrations."""
        return self.module_registry.require("flow_chat")

    @property
    def canvas_conversation_service(self) -> Any:
        """Return the registered canvas_conversation service for legacy integrations."""
        return self.module_registry.require("canvas_conversation")

    @property
    def global_response_mode(self) -> Any:
        """Read the conversation owner's default response policy."""
        return self.module_registry.require("chat_workspace").global_response_mode

    @global_response_mode.setter
    def global_response_mode(self, value: Any) -> None:
        """Forward a default policy update to the conversation owner."""
        self.module_registry.require("chat_workspace").global_response_mode = value
