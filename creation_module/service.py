"""Controlled orchestration for source-derived metadata and memory proposals."""

from collections.abc import Iterable, Sequence
from hashlib import sha256

from creation_module.errors import ApprovalError, SourceChangedError, ValidationError
from creation_module.interfaces import CreationGenerator, KnowledgeSourceService, MemoryProposalService, WorkspaceCreationService
from creation_module.models import CreationResult, FieldOrigin, MemoryBrickProposal, MetadataLayer
from creation_module.workspace_models import WorkspaceCreationRequest, WorkspaceCreationResult


class CreationModule:
    """Generate through adapters and persist only through explicit owner services."""

    def __init__(self, *, source_service: KnowledgeSourceService, memory_service: MemoryProposalService, generator: CreationGenerator, workspace_service: WorkspaceCreationService | None = None) -> None:
        self._source_service = source_service
        self._memory_service = memory_service
        self._generator = generator
        self._workspace_service = workspace_service

    def create_workspace_object(self, kind: str, request: str, *, chat_id: str | None, scope: str = "global") -> WorkspaceCreationResult:
        """Persist one approved workspace request using Core's already-fixed scope."""
        if self._workspace_service is None:
            raise RuntimeError("Workspace creation is unavailable.")
        clean_kind = kind.strip().lower()
        content = request.strip()
        scope = scope.strip().lower()
        if clean_kind not in {"sheet", "comment", "memory"} or not content:
            raise ValidationError("Workspace creation requires a sheet, comment, or memory request.")
        linked_chat_id = chat_id.strip() if isinstance(chat_id, str) and scope == "chat" else None
        if scope == "chat" and not linked_chat_id:
            raise ValidationError("Chat-scoped workspace creation requires a current chat.")
        title = ""
        if clean_kind == "sheet":
            title = self._workspace_fields(clean_kind, content, ("title",)).get("title", "").strip() or "New Sheet"
        creation = WorkspaceCreationRequest(clean_kind, title, "", content, scope, linked_chat_id)
        owner_method = getattr(self._workspace_service, f"create_{clean_kind}")
        created = owner_method(creation)
        return WorkspaceCreationResult((str(getattr(created, f"{clean_kind}_id", "")),))

    def generate_missing_metadata(self, source_id: str) -> CreationResult:
        source = self._source_service.get_source(source_id)
        targets = [layer for layer in MetadataLayer if source.metadata_field(layer).is_missing]
        preserved = tuple(layer.value for layer in MetadataLayer if layer not in targets)
        if not targets:
            return CreationResult(source_id, preserved_fields=preserved, message="No missing metadata fields.")
        return self._write_metadata(source, targets, preserved, "Missing metadata generated.")

    def refresh_generated_metadata(self, source_id: str, selected_layers: Sequence[MetadataLayer] | None = None, *, replace_manual: bool = False) -> CreationResult:
        source = self._source_service.get_source(source_id)
        targets, preserved = [], []
        for layer in selected_layers or list(MetadataLayer):
            field = source.metadata_field(layer)
            if field.is_missing or field.is_stale(source.source_hash) or (replace_manual and field.origin == FieldOrigin.MANUAL):
                targets.append(layer)
            else:
                preserved.append(layer.value)
        if not targets:
            return CreationResult(source_id, preserved_fields=tuple(preserved), message="No selected metadata fields required refresh.")
        return self._write_metadata(source, targets, tuple(preserved), "Selected metadata refreshed.")

    def regenerate_selected_metadata(self, source_id: str, layers: Sequence[MetadataLayer], *, replace_manual: bool = False) -> CreationResult:
        """Explicitly regenerate selected layers while retaining protected manual values."""
        source = self._source_service.get_source(source_id)
        targets = [layer for layer in layers if replace_manual or source.metadata_field(layer).origin != FieldOrigin.MANUAL]
        preserved = tuple(layer.value for layer in layers if layer not in targets)
        if not targets:
            return CreationResult(source_id, preserved_fields=preserved, message="All selected fields were protected manual fields.")
        return self._write_metadata(source, targets, preserved, "Selected metadata regenerated.")

    def categorize_source(self, source_id: str, *, apply_changes: bool = True):
        source = self._source_service.get_source(source_id)
        proposal = self._generator.categorize_source(source)
        if proposal.source_id != source.source_id or proposal.source_hash != source.source_hash:
            raise SourceChangedError("Categorization was generated for a different source version.")
        self._score(proposal.confidence, "categorization confidence")
        categorization = self._source_service.validate_categorization(proposal.categorization)
        if apply_changes:
            self._unchanged(source_id, source.source_hash)
            self._source_service.update_categorization(source_id=source_id, expected_source_hash=source.source_hash, categorization=categorization)
        return proposal.__class__(proposal.source_id, proposal.source_hash, categorization, proposal.confidence, proposal.rationale)

    def propose_memory_bricks(self, source_id: str) -> list[MemoryBrickProposal]:
        source = self._source_service.get_source(source_id)
        proposals = self._generator.propose_memory_bricks(source)
        seen: set[str] = set()
        for proposal in proposals:
            self._validate_proposal(proposal, source.source_id, source.source_hash)
            if proposal.proposal_id in seen:
                raise ValidationError(f"Duplicate proposal ID: {proposal.proposal_id}")
            seen.add(proposal.proposal_id)
        return proposals

    def create_approved_memory_bricks(self, source_id: str, proposals: Sequence[MemoryBrickProposal], approved_ids: Iterable[str]) -> CreationResult:
        source = self._source_service.get_source(source_id)
        approved = set(approved_ids)
        by_id = {item.proposal_id: item for item in proposals}
        if len(by_id) != len(proposals):
            raise ValidationError("Approved proposal input contains duplicate proposal IDs.")
        unknown = approved.difference(by_id)
        if unknown:
            raise ApprovalError(f"Approved proposal IDs were not supplied: {sorted(unknown)}")
        created, skipped = [], []
        for proposal in proposals:
            self._validate_proposal(proposal, source.source_id, source.source_hash)
            if proposal.proposal_id not in approved:
                skipped.append(proposal.proposal_id)
                continue
            self._unchanged(source_id, proposal.source_hash)
            created.append(self._memory_service.create_memory_from_proposal(proposal).memory_id)
        return CreationResult(source_id, created_memory_ids=tuple(created), skipped_proposal_ids=tuple(skipped), message=f"Created {len(created)} approved Memory Brick(s).")

    def _write_metadata(self, source, targets, preserved, message: str) -> CreationResult:
        generated = self._generator.generate_metadata(source, targets)
        if set(generated) != set(targets) or any(not value.strip() for value in generated.values()):
            raise ValidationError("Generator metadata output must contain exactly the requested non-empty layers.")
        self._unchanged(source.source_id, source.source_hash)
        self._source_service.update_metadata(source_id=source.source_id, expected_source_hash=source.source_hash, updates=generated, generated=True)
        return CreationResult(source.source_id, tuple(layer.value for layer in targets), preserved, message=message)

    def _workspace_fields(self, kind: str, request: str, fields: Sequence[str]) -> dict[str, str]:
        try:
            return self._generator.generate_workspace_fields(kind, request, fields)
        except Exception:
            return {}

    def _unchanged(self, source_id: str, expected_hash: str) -> None:
        if self._source_service.get_source(source_id).source_hash != expected_hash:
            raise SourceChangedError("Knowledge source changed after generation. Run the operation again.")

    @classmethod
    def _validate_proposal(cls, proposal: MemoryBrickProposal, source_id: str, source_hash: str) -> None:
        if proposal.source_id != source_id:
            raise ValidationError("Memory proposal source ID mismatch.")
        if proposal.source_hash != source_hash:
            raise SourceChangedError("Memory proposal was generated from an outdated source version.")
        if not proposal.content or not proposal.evidence or proposal.scope not in {"global", "chat", "module"}:
            raise ValidationError("Memory proposals require content, evidence, and a global, chat, or module scope.")
        cls._score(proposal.importance, "importance")
        cls._score(proposal.confidence, "confidence")

    @staticmethod
    def _score(value: float, name: str) -> None:
        if not 0.0 <= float(value) <= 1.0:
            raise ValidationError(f"{name} must be between 0.0 and 1.0.")
