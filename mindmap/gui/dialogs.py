"""Node, relationship, and chat-import editors owned by Mind Map."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from mindmap.models import GraphLink, GraphNode


NODE_TYPES = (
    "idea",
    "task",
    "decision",
    "feature",
    "bug",
    "reference",
    "container",
    "chat",
    "sheet",
    "comment",
    "material",
    "memory",
    "custom",
)

LINK_TYPES = (
    "related_to",
    "contains",
    "part_of",
    "depends_on",
    "supports",
    "contradicts",
    "derived_from",
    "references",
    "caused_by",
    "solves",
)


def _unit_spin(value: float) -> QDoubleSpinBox:
    """Create the shared unit-interval editor used by node and link dialogs."""
    spin = QDoubleSpinBox()
    spin.setRange(0.0, 1.0)
    spin.setDecimals(2)
    spin.setSingleStep(0.05)
    spin.setValue(value)
    return spin


class NodeDialog(QDialog):
    """Collect the minimum meaningful node properties for V1."""

    def __init__(self, parent: QWidget | None = None, node: GraphNode | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Node" if node else "Create Node")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_input = QLineEdit(node.title if node else "")
        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(NODE_TYPES)
        self.type_input.setCurrentText(node.node_type if node else "idea")
        if node is not None and node.source_reference is not None:
            # A source-backed node's type identifies its owning AMADEUS module.
            # Renaming a Sheet node to Memory here would not migrate the real
            # object, so type conversion remains a future explicit workflow.
            self.type_input.setEnabled(False)
            self.type_input.setToolTip("Source-backed node types cannot be converted in-place yet.")
        self.description_input = QTextEdit(node.description if node else "")
        self.description_input.setMaximumHeight(100)
        self.content_input = QTextEdit(node.content if node else "")
        self.content_input.setMaximumHeight(120)
        self.importance_input = self._unit_spin(node.importance if node else 0.5)
        self.confidence_input = self._unit_spin(node.confidence if node else 1.0)
        self.locked_input = QCheckBox()
        self.locked_input.setChecked(node.position_locked if node else False)
        self.workspace_object_input = QCheckBox("Create the matching real AMADEUS object")
        self.workspace_object_input.setToolTip(
            "For chat, sheet, comment, and memory types, create a real source-backed object instead of only a graph label."
        )
        self.workspace_object_input.setVisible(node is None)
        self.type_input.currentTextChanged.connect(self._update_workspace_option)
        self._update_workspace_option(self.type_input.currentText())

        form.addRow("Title:", self.title_input)
        form.addRow("Type:", self.type_input)
        form.addRow("Description:", self.description_input)
        form.addRow("Content:", self.content_input)
        form.addRow("Importance:", self.importance_input)
        form.addRow("Confidence:", self.confidence_input)
        form.addRow("Lock position:", self.locked_input)
        if node is None:
            form.addRow("Workspace object:", self.workspace_object_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "title": self.title_input.text().strip(),
            "node_type": self.type_input.currentText().strip(),
            "description": self.description_input.toPlainText().strip(),
            "content": self.content_input.toPlainText().strip(),
            "importance": self.importance_input.value(),
            "confidence": self.confidence_input.value(),
            "position_locked": self.locked_input.isChecked(),
            "create_workspace_object": self.workspace_object_input.isChecked(),
        }

    def _update_workspace_option(self, node_type: str) -> None:
        enabled = node_type.strip().lower() in {"chat", "sheet", "comment", "memory"}
        self.workspace_object_input.setEnabled(enabled)
        self.workspace_object_input.setChecked(enabled)
        if enabled:
            self.workspace_object_input.setText("Create the matching real AMADEUS object")
        else:
            self.workspace_object_input.setText("This type is graph-only")

    def _unit_spin(self, value: float) -> QDoubleSpinBox:
        return _unit_spin(value)


class LinkDialog(QDialog):
    """Collect first-class relationship properties."""

    def __init__(self, parent: QWidget | None = None, link: GraphLink | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Link" if link else "Create Link")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(LINK_TYPES)
        self.type_input.setCurrentText(link.link_type if link else "related_to")
        self.label_input = QLineEdit(link.label if link else "")
        self.strength_input = self._unit_spin(link.strength if link else 0.5)
        self.confidence_input = self._unit_spin(link.confidence if link else 1.0)
        self.permanence_input = self._unit_spin(link.permanence if link else 0.5)
        self.evidence_input = QTextEdit(link.evidence if link else "")
        self.evidence_input.setMaximumHeight(100)
        self.temporary_input = QCheckBox()
        self.temporary_input.setChecked(link.is_temporary if link else False)
        self._existing_metadata = dict(link.metadata) if link else {}
        self.inject_into_chat_input = QCheckBox("Automatically include this linked node in chat context")
        self.inject_into_chat_input.setChecked(self._existing_metadata.get("inject_into_chat", True) is not False)

        form.addRow("Relationship:", self.type_input)
        form.addRow("Visible label:", self.label_input)
        form.addRow("Strength:", self.strength_input)
        form.addRow("Confidence:", self.confidence_input)
        form.addRow("Permanence:", self.permanence_input)
        form.addRow("Evidence:", self.evidence_input)
        form.addRow("Temporary:", self.temporary_input)
        form.addRow("Chat context:", self.inject_into_chat_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "link_type": self.type_input.currentText().strip(),
            "label": self.label_input.text().strip(),
            "strength": self.strength_input.value(),
            "confidence": self.confidence_input.value(),
            "permanence": self.permanence_input.value(),
            "evidence": self.evidence_input.toPlainText().strip(),
            "is_temporary": self.temporary_input.isChecked(),
            "metadata": {
                **self._existing_metadata,
                "inject_into_chat": self.inject_into_chat_input.isChecked(),
            },
        }

    def _unit_spin(self, value: float) -> QDoubleSpinBox:
        return _unit_spin(value)


class ChatImportDialog(QDialog):
    """Choose dedicated chats to project into the Mind Map through Core."""

    def __init__(self, chats: list[object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import AMADEUS Chats")
        self.resize(520, 430)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Choose chats to represent as source-backed Mind Map nodes. "
            "Importing again updates metadata without creating duplicates."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.chat_list = QListWidget()
        self.chat_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for chat in chats:
            title = str(getattr(chat, "title", "Untitled Chat"))
            description = str(getattr(chat, "description", "")).strip()
            purpose = str(getattr(chat, "purpose", "General"))
            item = QListWidgetItem(f"{title}  ·  {purpose}")
            item.setToolTip(description or "No chat description")
            item.setData(Qt.ItemDataRole.UserRole, chat)
            self.chat_list.addItem(item)
            item.setSelected(True)
        layout.addWidget(self.chat_list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import Selected")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_chats(self) -> list[object]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.chat_list.selectedItems()]
