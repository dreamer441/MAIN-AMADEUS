"""PyQt6 view components for the AMADEUS Mind Map module.

The GUI is imported lazily so service, physics, and persistence tests can run in
headless environments without installing PyQt6.
"""

from __future__ import annotations


__all__ = ["MindMapView"]


def __getattr__(name: str):
    if name == "MindMapView":
        from mindmap.gui.view import MindMapView

        return MindMapView
    raise AttributeError(name)
