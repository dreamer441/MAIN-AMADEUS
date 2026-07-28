"""Lazy PyQt6 exports for the AMADEUS Canvas module."""

from __future__ import annotations

__all__ = ["CanvasView"]


def __getattr__(name: str):
    if name == "CanvasView":
        from canvas_module.gui.view import CanvasView

        return CanvasView
    raise AttributeError(name)
