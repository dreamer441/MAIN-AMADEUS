"""Typed parsing for the shared, approval-gated creation annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from annotation_module.annotation_parser import AnnotationParser


@dataclass(frozen=True, slots=True)
class CreationAnnotationRequest:
    """One explicit creation request prepared by Annotation Module, never persisted here."""

    kind: Literal["chat", "sheet", "memory"]
    request: str
    explicit_scope: Literal["chat", "global"] | None = None


def parse_creation_annotation(message: str) -> CreationAnnotationRequest | None:
    """Parse only supported creation forms and reject blank creation content."""
    stripped = message.strip()
    if stripped.startswith("/create-chat") and _has_boundary(stripped, "/create-chat"):
        return _request("chat", stripped[len("/create-chat"):])
    annotation = AnnotationParser().parse(stripped)
    if annotation is None or not annotation.arguments:
        return None
    command = AnnotationParser().normalize_token(annotation.arguments[0])
    if annotation.annotation_name == "sheet" and command == "create":
        return _request("sheet", annotation.content)
    if annotation.annotation_name == "memory" and command == "save":
        return _request("memory", annotation.content)
    return None


def _has_boundary(message: str, command: str) -> bool:
    return len(message) == len(command) or message[len(command)].isspace()


def _request(kind: Literal["chat", "sheet", "memory"], content: str) -> CreationAnnotationRequest | None:
    request = content.strip()
    before, marker, scope = request.rpartition("; scope:")
    explicit_scope = scope.strip().lower()
    if marker and before.strip() and explicit_scope in {"chat", "global"}:
        request = before.strip()
    else:
        explicit_scope = ""
    if not request:
        return None
    return CreationAnnotationRequest(kind=kind, request=request, explicit_scope=explicit_scope or None)
