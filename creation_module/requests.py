"""Prepare explicit or advisory workspace creation for approval."""

from __future__ import annotations

from typing import Any
from annotation_module import CreationAnnotationRequest
from creation_module.chat_metadata import FlowCreateChatRequest
from inner_brain import InnerBrainAnalysis
from permissions.pending_actions import PendingAction


class CreationRequestService:
    """Prepare explicit or advisory workspace creation for approval."""

    def __init__(self, *, chat_metadata_resolver: Any, permissions: Any, current_chat_id_provider: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.chat_metadata_resolver = chat_metadata_resolver
        self.permissions = permissions
        self.current_chat_id_provider = current_chat_id_provider

    def create_pending_creation_action(self, request: CreationAnnotationRequest, *, route: str) -> PendingAction:
        """Convert a typed annotation or advisory intent into one non-persistent action."""
        default_scope = "global" if route == "flow" else "chat"
        scope = request.explicit_scope or default_scope
        linked_chat_id = self.current_chat_id_provider() if scope == "chat" else ""
        fields: dict[str, Any] = {"request": request.request}
        if request.kind == "chat":
            parsed = FlowCreateChatRequest.parse(f"/create-chat {request.request}")
            draft = self.chat_metadata_resolver.resolve(parsed or FlowCreateChatRequest(request=request.request))
            fields = {"title": draft.title, "description": draft.description, "priority": draft.priority}
        return self.permissions.create_pending_action(
            kind=request.kind,
            fields=fields,
            scope=scope,
            linked_chat_id=linked_chat_id,
        )

    def pending_action_from_inference(
        self,
        analysis: InnerBrainAnalysis,
        message: str,
        *,
        route: str,
    ) -> PendingAction | None:
        """Map the bounded advisory creation kind to a fixed pending action."""
        if analysis.creation_kind not in {"chat", "sheet", "memory"}:
            return None
        # Treat the model as advisory only when the user's wording also asks to create/save.
        if not any(token in message.lower() for token in ("create", "make", "new", "save", "remember")):
            return None
        request = analysis.description or analysis.title or message
        return self.create_pending_creation_action(
            CreationAnnotationRequest(kind=analysis.creation_kind, request=request), route=route
        )

    @staticmethod
    def looks_like_creation_command(message: str) -> bool:
        """Keep malformed supported creation syntax local instead of sending it to the LLM."""
        lowered = message.strip().lower()
        return lowered.startswith("/create-chat") or lowered.startswith("[sheet][create]") or lowered.startswith("[memory][save]")
