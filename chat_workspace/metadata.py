"""Own explicit chat analysis, export references and Chat Data presentation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from inner_brain import InnerBrainAnalysis
from storage import ChatInnerBrainAnalysis, ChatMetadata


class ChatMetadataService:
    """Own explicit chat analysis, export references and Chat Data presentation."""

    def __init__(
        self,
        *,
        chat_history_store: Any,
        inner_brain_service: Any,
        export_service: Any,
        mind_map_workspace_sync: Any,
    ) -> None:
        """Receive the public services needed by this workflow."""
        self.chat_history_store = chat_history_store
        self.inner_brain_service = inner_brain_service
        self.export_service = export_service
        self.mind_map_workspace_sync = mind_map_workspace_sync

    def refresh_chat_inner_brain(self, chat_id: str | None = None) -> InnerBrainAnalysis:
        """Explicitly generate and persist the active chat's five analysis layers."""
        target_id = chat_id or self.chat_history_store.get_current_chat_id()
        chat = self.chat_history_store.get_chat(target_id)
        if chat is None:
            raise ValueError(f"Unknown chat id: {target_id}")
        transcript = "\n".join(f"{item.speaker}: {item.message}" for item in self.chat_history_store.load_messages(100000, target_id))
        analysis = self.inner_brain_service.analyze_chat(transcript)
        previous = chat.inner_brain_analysis
        record = ChatInnerBrainAnalysis(
            generated_at=datetime.now(timezone.utc).isoformat(), model=analysis.model,
            title=analysis.title, description=analysis.description,
            short_bullets=analysis.short_bullets, detailed_summary=analysis.detailed_summary,
            export_id=previous.export_id if previous is not None else "",
        )
        updated = self.chat_history_store.update_chat_metadata(
            target_id,
            title=analysis.title if not chat.title.strip() else None,
            description=analysis.description if not chat.description.strip() else None,
            inner_brain_analysis=record,
        )
        self.mind_map_workspace_sync.sync_chat(updated)
        return analysis

    def create_chat_inner_brain_export(self, chat_id: str | None = None) -> ChatMetadata:
        """Create an export only from the explicit Chat Data action."""
        target_id = chat_id or self.chat_history_store.get_current_chat_id()
        chat = self.chat_history_store.get_chat(target_id)
        if chat is None:
            raise ValueError(f"Unknown chat id: {target_id}")
        export = self.export_service.export_chat(target_id)
        previous = chat.inner_brain_analysis
        record = previous or ChatInnerBrainAnalysis(
            generated_at=datetime.now(timezone.utc).isoformat(), model="nemotron-3-nano:4b"
        )
        updated = self.chat_history_store.update_chat_metadata(
            target_id,
            inner_brain_analysis=ChatInnerBrainAnalysis(
                generated_at=record.generated_at, model=record.model, title=record.title,
                description=record.description, short_bullets=record.short_bullets,
                detailed_summary=record.detailed_summary, export_id=export.export_id,
            ),
        )
        self.mind_map_workspace_sync.sync_chat(updated)
        return updated

    def get_chat_data_panel_payload(self, suggested_write_actions: tuple[str, ...] = ()) -> dict[str, Any]:
        """Return display-only Chat Data state for the active chat side-panel tab."""
        chat = self.chat_history_store.get_current_chat()
        analysis = chat.inner_brain_analysis
        return {"type": "inner_brain", "title": "Chat Data", "content": "", "metadata": {
            "chat_id": chat.chat_id, "title": chat.title, "description": chat.description,
            "short_bullets": list(analysis.short_bullets) if analysis else [],
            "detailed_summary": analysis.detailed_summary if analysis else "",
            "export_id": analysis.export_id if analysis else "",
            "generated_at": analysis.generated_at if analysis else "",
            "model": analysis.model if analysis else "nemotron-3-nano:4b",
            "suggested_write_actions": list(suggested_write_actions),
        }}
