"""Small state holder for the AMADEUS right-side panel.

The state is deliberately simple. It remembers what the panel is showing so
future features such as `[panel]` can ask for the current visible context without
needing to scrape PyQt widgets directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from side_panel.side_panel_payload import SidePanelPayload


@dataclass(slots=True)
class SidePanelState:
    """Tracks the latest visible side-panel payloads.

    This does not persist data to disk yet. It is runtime workspace state:
    current active tab, latest trace, opened code, memory, sheets, and future
    material payloads. Persistent data remains owned by each real module.
    """

    active_tab: str = "process"
    compact_trace: str = "Process Monitor will show the latest message trace here."
    detailed_trace: str = "Process Monitor will show the latest message trace here."
    code_payload: SidePanelPayload | None = None
    memory_payload: SidePanelPayload | None = None
    sheets_payload: SidePanelPayload | None = None
    materials_payload: SidePanelPayload | None = None
    current_chat_context: str = "Current Chat Context\nMetadata unavailable."
    extra_payloads: dict[str, SidePanelPayload] = field(default_factory=dict)

    def set_trace(self, compact: str, detailed: str | None = None) -> None:
        """Store the latest trace text and mark Process Monitor as active."""
        self.compact_trace = compact
        self.detailed_trace = detailed or compact
        self.active_tab = "process"

    def set_payload(self, payload: SidePanelPayload) -> None:
        """Store one payload according to its type.

        Known panel types get named slots. Unknown future types are preserved in
        `extra_payloads` so adding more panels later does not require a destructive
        redesign.
        """
        normalized_type = payload.panel_type.strip().lower()
        self.active_tab = normalized_type
        if normalized_type == "code":
            self.code_payload = payload
        elif normalized_type == "memory":
            self.memory_payload = payload
        elif normalized_type == "sheets":
            self.sheets_payload = payload
        elif normalized_type == "materials":
            self.materials_payload = payload
        else:
            self.extra_payloads[normalized_type] = payload

    def set_chat_context(self, context_text: str) -> None:
        """Update visible chat context used by the Memory tab."""
        self.current_chat_context = context_text

    def reset_for_chat_switch(self, chat_context_text: str) -> None:
        """Clear chat-specific visible state when Dato switches chats."""
        default_trace = "Process Monitor will show the latest message trace here."
        self.active_tab = "process"
        self.compact_trace = default_trace
        self.detailed_trace = default_trace
        self.code_payload = None
        self.memory_payload = None
        self.sheets_payload = None
        self.materials_payload = None
        self.extra_payloads.clear()
        self.current_chat_context = chat_context_text

    def current_context_text(self) -> str:
        """Return readable state for future `[panel]` context injection.

        `[panel]` is not implemented in this patch, but this method is the stable
        foundation it will use later. It returns only visible panel data, not
        hidden model reasoning.
        """
        lines = [f"Active side panel: {self.active_tab}"]
        if self.active_tab == "code" and self.code_payload is not None:
            lines.append(f"Code Viewer: {self.code_payload.title}")
            lines.append(self.code_payload.content)
        elif self.active_tab == "memory":
            lines.append("Memory Panel:")
            lines.append(self.current_chat_context)
            if self.memory_payload is not None and self.memory_payload.content.strip():
                lines.append(self.memory_payload.content)
        elif self.active_tab == "sheets" and self.sheets_payload is not None:
            lines.append(f"Sheets Panel: {self.sheets_payload.title}")
            lines.append(self.sheets_payload.content)
        elif self.active_tab == "materials" and self.materials_payload is not None:
            lines.append(f"Materials Panel: {self.materials_payload.title}")
            lines.append(self.materials_payload.content)
        else:
            lines.append("Process Monitor:")
            lines.append(self.compact_trace)
        return "\n".join(lines)
