"""Typed public models for the AMADEUS Canvas module."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanvasWorkspaceDescriptor:
    """Describe one Canvas workspace without exposing GUI or persistence internals.

    The first Canvas phase only exposes a stable workspace identity and visible
    module purpose. Later phases can extend the module behind this public model
    with structured objects, persistence, revisions, and context extraction.
    """

    workspace_id: str
    title: str
    purpose: str
    status: str
    schema_version: int = 1
