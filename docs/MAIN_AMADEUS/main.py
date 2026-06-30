import sys

from PyQt6.QtWidgets import QApplication

from amadeus_core import AmadeusCore
from amadeus_gui import AmadeusMainWindow


def main() -> int:
    """Start AMADEUS Core, create the GUI, and run the desktop event loop."""
    app = QApplication(sys.argv)

    # Core is created before the GUI so the GUI can route all user actions through it.
    core = AmadeusCore()
    window = AmadeusMainWindow(core)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
