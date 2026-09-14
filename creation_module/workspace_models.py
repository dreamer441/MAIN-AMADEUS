"""Validated workspace creation values owned by the Creation Module."""

from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class WorkspaceCreationRequest:
    """One validated immediate creation request sent through the Core-owned port."""

    kind: str
    title: str
    description: str
    content: str
    scope: str
    chat_id: str | None
    selected_text: str = ""


@dataclass(frozen=True, slots=True)
class WorkspaceCreationResult:
    """Owner-created records returned after immediate creation."""

    created_ids: tuple[str, ...] = ()
    skipped_proposal_ids: tuple[str, ...] = ()
