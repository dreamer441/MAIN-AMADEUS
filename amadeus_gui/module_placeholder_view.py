"""Purposeful placeholder pages for AMADEUS modules not yet exposed in the GUI."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ModulePlaceholderView(QWidget):
    """Show the named module and make its pending foundation explicit."""

    def __init__(self, module_name: str, purpose: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.module_name = module_name

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(module_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        detail = QLabel(f"{purpose}\nFoundation pending.")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        detail.setStyleSheet("color: #666; font-size: 15px;")
        layout.addWidget(title)
        layout.addWidget(detail)
