"""
AMADEUS V2 - main.py

Purpose:
    Provide the tiny process entry point for AMADEUS V2 Core.

Responsibilities:
    - Create the AMADEUS application object.
    - Start AMADEUS Core.
    - Return a normal process exit code.

Must NOT:
    - Implement Core startup details.
    - Import module or submodule internals.
    - Contain feature logic.

Connected systems:
    - amadeus_core/app.py
    - amadeus_core/core_controller.py
"""

from amadeus_core.app import AmadeusApp


def main() -> int:
    """
    Input:
        None.
    Output:
        Process exit code.
    Side effects:
        Starts AMADEUS Core and writes startup logs.
    """
    app = AmadeusApp()
    app.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
