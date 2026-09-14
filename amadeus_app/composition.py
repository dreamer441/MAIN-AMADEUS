"""Construct the application once and connect explicit public owner services.

Only this startup module knows the complete dependency graph. It never receives
user requests; Core routes those requests to the owners registered here.
"""

from pathlib import Path

from amadeus_core.module_registry import ModuleRegistry
from amadeus_chat import AmadeusChatModule
from annotation_module import AnnotationContext, AnnotationParser, AnnotationRegistry, AnnotationSuggestionService
from annotation_module.annotations import ExportAnnotation, FileAnnotation, IdentityAnnotation, MemoryAnnotation, MetadataAnnotation, MindMapAnnotation, SheetAnnotation
from annotation_module.suggestions import AnnotationSuggestions
from canvas_module import CanvasConversationService, CanvasModule
from canvas_module.request_handler import CanvasRequestHandler
from chat_registry import ChatRegistry
from chat_workspace.conversation import ChatConversation
from chat_workspace.documents import WorkspaceDocuments
from chat_workspace.exchanges import ExchangePersistence
from chat_workspace.lifecycle import ChatLifecycle
from chat_workspace.metadata import ChatMetadataService
from chat_workspace.selected_context import SelectedContextConversation
from comments_module import CommentService
from context_builder import ChatContextBuilder
from context_builder.inferred_context import InferredContextAdvisor
from creation_module import CreationModule, OllamaCreationGenerator
from creation_module.approved_actions import ApprovedCreationActions
from creation_module.requests import CreationRequestService
from export_module import ChatExportService
from flow_chat import FlowChatService, FlowChatStore, FlowContextBuilder, FlowReviewContextBuilder, FlowHabitRequestService
from creation_module.chat_metadata import FlowChatMetadataResolver
from flow_chat.request_handler import FlowRequestHandler
from habit_tracker.actions import HabitActionExecutor
from habit_tracker.service import HabitTrackerService
from identity_module import IdentityPromptBuilder, IdentityService
from inner_brain import InnerBrainService
from llm_client import OllamaClient
from materials_module import MaterialsService
from materials_module.workspace import MaterialsWorkspace
from memory_module import MemoryService
from memory_module.creation_adapter import MemoryKnowledgeSourceAdapter, MemoryProposalAdapter
from mindmap import MindMapModule
from permissions import PermissionGuard, PendingActionService
from project_file_reader import ProjectFileReader
from project_file_reader.workspace import ProjectFileWorkspace
from response_modes import ResponseMode
from response_modes.response_payload import ResponsePresenter
from side_ask_module import SideAskService
from side_ask_module.workflow import SideAskWorkflow
from sheets_module import SheetService
from storage import ChatHistoryStore
from workspace_integration import MindMapWorkspaceSync
from workspace_integration.creation_adapter import WorkspaceCreationAdapter
from workspace_integration.graph_workspace import GraphWorkspace


def compose_application(
    project_root: Path,
    llm_client: object | None = None,
    inner_brain_service: object | None = None,
) -> ModuleRegistry:
    """Create a dependency-complete registry without exposing Core to internals."""
    registry = ModuleRegistry()
    llm = llm_client or OllamaClient()
    brain = inner_brain_service or InnerBrainService(OllamaClient(model="nemotron-3-nano:4b"))
    reader = ProjectFileReader(project_root)
    identity = IdentityService(project_root)
    identity_prompts = IdentityPromptBuilder(identity)
    history = ChatHistoryStore(project_root)
    flow_history = FlowChatStore(project_root)
    chats = ChatRegistry(history)
    memory = MemoryService(project_root)
    sheets = SheetService(project_root)
    comments = CommentService(project_root)
    exports = ChatExportService(project_root, history)
    materials = MaterialsService(project_root, exports)
    side_ask = SideAskService()
    canvas = CanvasModule(project_root)
    graph = MindMapModule(project_root)
    habits = HabitTrackerService(project_root)
    flow_habits = FlowHabitRequestService(habits)

    sync = MindMapWorkspaceSync(mind_map_module=graph, chat_history_store=history,
        sheet_service=sheets, comment_service=comments, memory_service=memory, canvas_module=canvas)
    canvas.subscribe(sync.handle_canvas_event)
    sync.reconcile_canvas_projection()
    creation = CreationModule(
        source_service=MemoryKnowledgeSourceAdapter(memory),
        memory_service=MemoryProposalAdapter(memory, on_created=sync.sync_memory),
        generator=OllamaCreationGenerator(llm),
        workspace_service=WorkspaceCreationAdapter(sheet_service=sheets,
            comment_service=comments, memory_service=memory, workspace_sync=sync),
    )
    context = ChatContextBuilder(chat_history_store=history, file_reader=reader,
        memory_service=memory, linked_context_provider=sync.build_linked_context)
    flow_context = FlowContextBuilder(flow_history, chats, FlowReviewContextBuilder(project_root, reader))
    parser = AnnotationParser()
    annotations = AnnotationRegistry()
    for name, handler in (
        ("file", FileAnnotation()), ("identity", IdentityAnnotation()),
        ("memory", MemoryAnnotation()), ("metadata", MetadataAnnotation()),
        ("sheet", SheetAnnotation()), ("export", ExportAnnotation()), ("mindmap", MindMapAnnotation()),
    ):
        annotations.register(name, handler)
    annotation_context = AnnotationContext(project_root=project_root, file_reader=reader,
        identity_service=identity, memory_service=memory, sheet_service=sheets,
        export_service=exports, mind_map_module=graph, annotation_parser=parser,
        current_chat_id_provider=history.get_current_chat_id, memory_saved_callback=sync.sync_memory)
    suggestions = AnnotationSuggestionService(file_reader=reader, parser=parser,
        sheet_service=sheets, export_service=exports, current_chat_id_provider=history.get_current_chat_id)
    advisor = InferredContextAdvisor(inner_brain_service=brain, annotation_parser=parser,
        annotation_registry=annotations, annotation_context=annotation_context)
    responses = ResponsePresenter()
    exchanges = ExchangePersistence(chat_history_store=history)
    lifecycle = ChatLifecycle(chat_history_store=history, mind_map_workspace_sync=sync)
    metadata = ChatMetadataService(chat_history_store=history, inner_brain_service=brain,
        export_service=exports, mind_map_workspace_sync=sync)
    pending = PendingActionService()
    permissions = PermissionGuard(pending, history.get_current_chat_id)
    approved_creation = ApprovedCreationActions(lifecycle=lifecycle, metadata=metadata, creation=creation)
    habit_actions = HabitActionExecutor(habit_tracker_service=habits)
    permissions.register_handler("chat", approved_creation.create_chat)
    for kind in ("sheet", "comment", "memory"):
        permissions.register_handler(kind, approved_creation.create_workspace)
    permissions.register_handler("export", approved_creation.create_export)
    permissions.register_handler("habit_tracker", lambda action: habit_actions.execute(dict(action.fields)))
    chat_metadata = FlowChatMetadataResolver(llm)
    creation_requests = CreationRequestService(chat_metadata_resolver=chat_metadata,
        permissions=permissions, current_chat_id_provider=history.get_current_chat_id)

    chat = AmadeusChatModule(llm_client=llm)
    registry.register("chat", chat)
    # A public provider permits replacement of the Chat implementation by name.
    chat_provider = lambda: registry.get("chat")
    selected_context = SelectedContextConversation(current_chat_id_provider=history.get_current_chat_id,
        sheet_service=sheets, export_service=exports, mind_map_module=graph,
        context_builder=context, identity_prompt_builder=identity_prompts,
        chat_module_provider=chat_provider, persist_exchange=exchanges.persist_exchange,
        build_response=responses.build_response_payload,
        response_decision_provider=lambda: conversation.resolve_response_mode())
    conversation = ChatConversation(annotation_parser=parser, annotation_registry=annotations,
        annotation_context=annotation_context, callable_context_router=selected_context,
        context_builder=context, identity_prompt_builder=identity_prompts,
        chat_module_provider=chat_provider, advisor=advisor, creation_requests=creation_requests,
        exchanges=exchanges, responses=responses, metadata=metadata,
        chat_history_store=history, global_response_mode=ResponseMode.NORMAL)
    flow = FlowChatService(chat_module=chat, flow_context_builder=flow_context,
        flow_chat_store=flow_history, identity_prompt_builder=identity_prompts,
        inferred_read_context_provider=None)
    canvas_conversation = CanvasConversationService(canvas_module=canvas, llm_client=llm)

    # Names are explicit startup contracts, not names supplied by a model or GUI.
    owners = {
        "flow_chat": flow, "flow_context_builder": flow_context, "chat_registry": chats,
        "identity": identity, "memory": memory, "creation": creation, "habit_tracker": habits,
        "sheets": sheets, "materials": materials, "exports": exports, "side_ask": side_ask,
        "comments": comments, "canvas": canvas, "canvas_conversation": canvas_conversation,
        "mind_map": graph, "context_builder": context, "chat_workspace": conversation,
        "chat_lifecycle": lifecycle, "chat_metadata": metadata,
        "workspace_documents": WorkspaceDocuments(chat_history_store=history, sheet_service=sheets,
            comment_service=comments, mind_map_workspace_sync=sync),
        "graph_workspace": GraphWorkspace(mind_map_module=graph, mind_map_workspace_sync=sync),
        "flow_requests": FlowRequestHandler(flow_habit_requests=flow_habits, flow_chat_store=flow_history,
            flow_chat_service=flow, annotation_parser=parser, annotation_registry=annotations,
            annotation_context=annotation_context, permissions=permissions,
            creation_requests=creation_requests, advisor=advisor, responses=responses),
        "canvas_requests": CanvasRequestHandler(canvas_conversation_service=canvas_conversation,
            identity_prompt_builder=identity_prompts, responses=responses),
        "side_ask_workflow": SideAskWorkflow(chat_module_provider=chat_provider, context_builder=context,
            identity_prompt_builder=identity_prompts, side_ask_service=side_ask,
            chat_history_store=history, responses=responses),
        "project_workspace": ProjectFileWorkspace(file_reader=reader, handle_user_message=conversation.handle_user_message),
        "materials_workspace": MaterialsWorkspace(materials_service=materials, handle_user_message=conversation.handle_user_message),
        "annotation_suggestions": AnnotationSuggestions(annotation_suggestion_service=suggestions),
        "creation_requests": creation_requests, "permissions": permissions, "pending_actions": pending,
        "history": history, "flow_history": flow_history, "file_reader": reader,
        "identity_prompts": identity_prompts, "inner_brain": brain, "llm_client": llm,
        "annotations": annotations, "annotation_parser": parser, "annotation_context": annotation_context,
        "suggestion_service": suggestions, "selected_context": selected_context, "advisor": advisor,
        "workspace_sync": sync, "responses": responses, "exchanges": exchanges,
        "chat_metadata_resolver": chat_metadata, "flow_habit_requests": flow_habits,
    }
    for name, owner in owners.items():
        registry.register(name, owner)
    return registry
