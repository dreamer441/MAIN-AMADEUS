"""Editors and context preview dialogs for the Canvas workspace."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from canvas_module import DEFAULT_RELATION_TYPE, CanvasConnector, CanvasContextPackage

from .constants import _RELATION_TYPES


class ConnectorEditorDialog(QDialog):
    """Small editor for the semantic metadata carried by a connector."""

    def __init__(self, connector: CanvasConnector, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Canvas Connector")
        self.resize(440, 330)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox()
        self.type_combo.addItem("Directional arrow", "arrow")
        self.type_combo.addItem("Plain relationship line", "line")
        type_index = self.type_combo.findData(connector.connector_type)
        self.type_combo.setCurrentIndex(max(0, type_index))

        self.relation_combo = QComboBox()
        self.relation_combo.setEditable(True)
        for relation_type in _RELATION_TYPES:
            self.relation_combo.addItem(relation_type.replace("_", " "), relation_type)
        relation_index = self.relation_combo.findData(connector.relation_type)
        if relation_index >= 0:
            self.relation_combo.setCurrentIndex(relation_index)
        else:
            self.relation_combo.setEditText(connector.relation_type.replace("_", " "))

        self.label_edit = QLineEdit(connector.label)
        self.label_edit.setPlaceholderText("Optional visible label")
        self.comment_edit = QTextEdit(connector.comment)
        self.comment_edit.setPlaceholderText("Optional explanation of why this relationship exists")

        form.addRow("Connector type", self.type_combo)
        form.addRow("Relation type", self.relation_combo)
        form.addRow("Visible label", self.label_edit)
        form.addRow("Comment", self.comment_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        relation_text = self.relation_combo.currentText().strip().lower().replace(" ", "_")
        return {
            "connector_type": str(self.type_combo.currentData()),
            "relation_type": relation_text or DEFAULT_RELATION_TYPE,
            "label": self.label_edit.text().strip(),
            "comment": self.comment_edit.toPlainText().strip(),
        }


class CanvasContextPreviewDialog(QDialog):
    """Human-readable inspection of the exact structured Canvas context."""

    def __init__(self, package: CanvasContextPackage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Canvas Context Preview")
        self.resize(760, 680)

        layout = QVBoxLayout(self)
        summary = QLabel(
            f"Mode: {package.context_mode.title()}  •  "
            f"Targets: {len(package.target_object_ids)} block(s), "
            f"{len(package.target_connector_ids)} connector(s)  •  "
            f"Estimated size: {package.estimated_tokens} tokens"
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("font-weight: 600; color: #dce7f2;")
        layout.addWidget(summary)

        explanation = QLabel(
            "AMADEUS will answer the response targets. Directional ancestors, descendants, and line-connected "
            "peers are supporting context only. The visible viewport limits what supporting information is eligible."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #8fa0b2;")
        layout.addWidget(explanation)

        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        preview.setPlainText(self._format_package(package))
        layout.addWidget(preview, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _format_package(package: CanvasContextPackage) -> str:
        blocks = {block.object_id: block for block in package.objects}

        def lines_for(title: str, object_ids: tuple[str, ...]) -> list[str]:
            result = [title]
            if not object_ids:
                result.append("  (none)")
            for object_id in object_ids:
                block = blocks.get(object_id)
                if block is None:
                    text = object_id
                else:
                    parts = [block.title, block.text, block.comment]
                    text = " | ".join(part.replace("\n", " ") for part in parts if part)
                if len(text) > 150:
                    text = text[:147] + "..."
                root_marker = " [ROOT]" if object_id == package.root_object_id else ""
                result.append(f"  • {text}{root_marker}\n    ID: {object_id}")
            return result

        sections: list[str] = []
        sections.extend(lines_for("RESPONSE TARGETS", package.target_object_ids))
        sections.append("")
        sections.extend(lines_for("DIRECTIONAL ANCESTORS (arrow history)", package.ancestor_object_ids))
        sections.append("")
        sections.extend(lines_for("DIRECTIONAL DESCENDANTS (arrow follow-ups)", package.descendant_object_ids))
        sections.append("")
        sections.extend(lines_for("RELATED PEERS (plain lines)", package.peer_object_ids))
        sections.append("")

        sections.append("TARGET CONNECTORS")
        target_connector_set = set(package.target_connector_ids)
        target_connectors = [
            connector for connector in package.connectors if connector.connector_id in target_connector_set
        ]
        if not target_connectors:
            sections.append("  (none)")
        for connector in target_connectors:
            sections.append(
                f"  • {connector.connector_type}: {connector.source_object_id} -> {connector.target_object_id} "
                f"[{connector.relation_type}] {connector.label}".rstrip()
            )

        sections.append("")
        sections.append("CHANGES REMOVED SINCE LAST SENT BASELINE")
        if not package.deleted_object_ids and not package.deleted_connector_ids:
            sections.append("  (none)")
        for object_id in package.deleted_object_ids:
            sections.append(f"  • Deleted block: {object_id}")
        for connector_id in package.deleted_connector_ids:
            sections.append(f"  • Deleted connector: {connector_id}")

        sections.append("")
        sections.append("VISIBLE BUT EXCLUDED AS UNRELATED")
        if not package.excluded_visible_object_ids:
            sections.append("  (none)")
        for object_id in package.excluded_visible_object_ids:
            sections.append(f"  • {object_id}")

        sections.append("")
        sections.append("TRIMMED BY CONTEXT BUDGET")
        if not package.trimmed_object_ids:
            sections.append("  (none)")
        for object_id in package.trimmed_object_ids:
            sections.append(f"  • {object_id}")

        if package.warnings:
            sections.append("")
            sections.append("WARNINGS")
            sections.extend(f"  • {warning}" for warning in package.warnings)
        return "\n".join(sections)


class CanvasTextEditor(QTextEdit):
    """Text editor where Enter submits and Shift+Enter inserts a line break."""

    submit_requested = pyqtSignal()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            modifiers = event.modifiers()
            if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                self.submit_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class CanvasTextEditorDialog(QDialog):
    """Focused create/edit dialog with fast Enter-to-commit behavior."""

    def __init__(
        self,
        *,
        title: str,
        label: str,
        initial_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 300)

        layout = QVBoxLayout(self)
        prompt = QLabel(label)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.editor = CanvasTextEditor()
        self.editor.setPlainText(initial_text)
        self.editor.setPlaceholderText("Type the Canvas content…")
        self.editor.submit_requested.connect(self._accept_non_empty)
        layout.addWidget(self.editor, stretch=1)

        hint = QLabel("Enter creates/saves the block  •  Shift+Enter adds a new line")
        hint.setStyleSheet("color: #7f8a99;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_non_empty)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.editor.setFocus()
        self.editor.moveCursor(QTextCursor.MoveOperation.End)

    def _accept_non_empty(self) -> None:
        if self.editor.toPlainText().strip():
            self.accept()

    def text(self) -> str:
        return self.editor.toPlainText().strip()
