"""Reusable GUI confirmation surface for Core-owned pending actions."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget


class ActionApprovalDialog(QDialog):
    """Render safe pending-action metadata and expose Approve or Decline only."""

    def __init__(self, approval_request: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Approve AMADEUS Action")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("AMADEUS needs your approval before making this change."))
        form = QFormLayout()
        form.addRow("Action:", QLabel(str(approval_request.get("kind", "unknown")).title()))
        form.addRow("Scope:", QLabel(str(approval_request.get("scope", "global"))))
        linked_chat_id = str(approval_request.get("linked_chat_id", ""))
        form.addRow("Linked chat:", QLabel(linked_chat_id or "Not linked"))
        fields = approval_request.get("display_fields")
        if isinstance(fields, dict):
            for key, value in fields.items():
                form.addRow(f"{str(key).replace('_', ' ').title()}:", QLabel(str(value)))
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Approve")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Decline")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
