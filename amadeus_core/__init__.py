"""
AMADEUS V2 - __init__.py

Purpose:
    Mark amadeus_core as the Core package for AMADEUS V2.

Responsibilities:
    - Expose the Core package version.
    - Keep package-level setup minimal and predictable.

Must NOT:
    - Start the application automatically.
    - Import module or submodule internals.
    - Contain feature logic.

Connected systems:
    - app.py
    - core_controller.py
"""

__version__ = "0.1.0-core"
