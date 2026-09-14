"""Independent top-level window lifecycle for AMADEUS feature modules.

Flow Chat remains inside the primary AMADEUS window. This manager owns one
persistent top-level window per major module and reuses the same module view
whenever Dato reopens it. Reusing views is essential: Canvas, Mind Map, Chats,
and future modules must never fork into duplicate state just because their
window was opened twice.
"""

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QMainWindow, QWidget


@dataclass(slots=True)
class ModuleWindowRegistration:
    """Describe one reusable module view and its top-level window settings."""

    key: str
    title: str
    view: QWidget
    size: tuple[int, int]
    on_show: Callable[[], None] | None = None


class ModuleWindow(QMainWindow):
    """A non-destructive top-level host for one existing module view.

    Qt does not delete a normal top-level window on close unless
    ``WA_DeleteOnClose`` is enabled. Keeping deletion disabled lets the manager
    reopen the exact same window and view, preserving drafts, selections,
    viewport state, and live module workers.
    """

    def __init__(self, registration: ModuleWindowRegistration) -> None:
        super().__init__()
        self.module_key = registration.key
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle(f"AMADEUS — {registration.title}")
        self.resize(*registration.size)
        self.setCentralWidget(registration.view)


class ModuleWindowManager(QObject):
    """Create, focus, hide, and close one shared window per AMADEUS module."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._registrations: dict[str, ModuleWindowRegistration] = {}
        self._windows: dict[str, ModuleWindow] = {}

    def register(
        self,
        key: str,
        title: str,
        view: QWidget,
        *,
        size: tuple[int, int] = (1100, 720),
        on_show: Callable[[], None] | None = None,
    ) -> None:
        """Register one stable module view without constructing its window yet."""
        clean_key = str(key or "").strip().lower()
        if not clean_key:
            raise ValueError("Module window key cannot be empty.")
        if clean_key in self._registrations:
            raise ValueError(f"Module window '{clean_key}' is already registered.")
        if not isinstance(view, QWidget):
            raise TypeError("Module window view must be a QWidget.")

        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("Module window size must contain positive values.")

        self._registrations[clean_key] = ModuleWindowRegistration(
            key=clean_key,
            title=str(title or clean_key).strip() or clean_key,
            view=view,
            size=(int(width), int(height)),
            on_show=on_show,
        )

    def open(self, key: str) -> ModuleWindow:
        """Show or focus the registered module without creating duplicates."""
        clean_key = str(key or "").strip().lower()
        registration = self._registrations.get(clean_key)
        if registration is None:
            raise KeyError(f"Unknown module window: {clean_key}")

        window = self._windows.get(clean_key)
        if window is None:
            window = ModuleWindow(registration)
            self._windows[clean_key] = window

        if registration.on_show is not None:
            registration.on_show()

        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()
        return window

    def focus(self, key: str) -> ModuleWindow:
        """Alias for :meth:`open`, documenting focus-oriented callers."""
        return self.open(key)

    def get_window(self, key: str) -> ModuleWindow | None:
        """Return an already-created module window without opening it."""
        return self._windows.get(str(key or "").strip().lower())

    def is_visible(self, key: str) -> bool:
        """Return whether the module's top-level window is currently visible."""
        window = self.get_window(key)
        return bool(window is not None and window.isVisible())

    def close(self, key: str) -> None:
        """Close one module window while preserving its reusable view instance."""
        window = self.get_window(key)
        if window is not None:
            window.close()

    def close_all(self) -> None:
        """Close every created module window during final AMADEUS shutdown."""
        for window in tuple(self._windows.values()):
            window.close()

    def registered_keys(self) -> tuple[str, ...]:
        """Expose stable registration order for diagnostics and focused tests."""
        return tuple(self._registrations)
