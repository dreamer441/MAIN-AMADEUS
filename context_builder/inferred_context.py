"""Resolve bounded advisory context through existing annotation handlers."""

from __future__ import annotations

from annotation_module import AnnotationResult, ParsedAnnotation
from inner_brain import InnerBrainAnalysis
from typing import Any
from annotation_module.annotation_result import unpack_annotation_output


class InferredContextAdvisor:
    """Resolve bounded advisory context through existing annotation handlers."""

    def __init__(
        self,
        *,
        inner_brain_service: Any,
        annotation_parser: Any,
        annotation_registry: Any,
        annotation_context: Any,
    ) -> None:
        """Receive the public services needed by this workflow."""
        self.inner_brain_service = inner_brain_service
        self.annotation_parser = annotation_parser
        self.annotation_registry = annotation_registry
        self.annotation_context = annotation_context

    def analyze_plain_message(self, message: str, route: str = "chat") -> InnerBrainAnalysis:
        """Ask the advisory model only after explicit annotation syntax has been ruled out."""
        try:
            result = self.inner_brain_service.analyze_message(message, route=route)
            return result if isinstance(result, InnerBrainAnalysis) else InnerBrainAnalysis()
        except Exception:
            return InnerBrainAnalysis()

    def build_flow_inferred_read_context(self, message: str) -> str | None:
        """Return only Flow's bounded read context from the existing no-argument handler."""
        analysis = self.analyze_plain_message(message, route="flow")
        if analysis.read_annotation == "metadata":
            return None
        return self.combine_callable_context(None, self.resolve_inferred_read_context(analysis))

    def resolve_inferred_read_context(self, analysis: InnerBrainAnalysis) -> str | None:
        """Run only no-argument, existing read handlers; model output never supplies a locator."""
        if analysis.read_annotation not in {"file", "sheet", "export", "mindmap"}:
            return None
        try:
            annotation = self.annotation_parser.parse(f"[{analysis.read_annotation}]")
            if annotation is None:
                return None
            output = self.annotation_registry.handle(annotation, self.annotation_context)
            response, _side_panel = unpack_annotation_output(output)
            return response[:6000] if response else None
        except Exception:
            return None

    def resolve_inferred_metadata(
        self,
        analysis: InnerBrainAnalysis,
        route: str = 'chat',
    ) -> AnnotationResult | None:
        """Reuse the verified metadata handler only for bounded general-chat intent."""
        if (
            route != "chat"
            or analysis.read_annotation != "metadata"
            or analysis.metadata_mode not in {"open", "answer"}
            or analysis.metadata_document_kind not in {"features", "future", "both"}
        ):
            return None
        arguments = (
            ["all", analysis.metadata_document_kind]
            if not analysis.metadata_module
            else ["module", analysis.metadata_module, analysis.metadata_document_kind]
        )
        try:
            annotation = ParsedAnnotation("metadata", arguments, "", normalized_arguments=list(arguments))
            output = self.annotation_registry.handle(annotation, self.annotation_context)
            response, side_panel = unpack_annotation_output(output)
            if not isinstance(side_panel, dict) or not isinstance(side_panel.get("content"), str):
                return None
            return AnnotationResult(response, side_panel)
        except Exception:
            return None

    @staticmethod
    def combine_callable_context(existing: str | None, inferred: str | None) -> str | None:
        """Keep advisory retrieved context bounded and separate from explicit caller context."""
        if not inferred:
            return existing
        inferred_block = "[SAFE INFERRED READ CONTEXT]\n" + inferred
        return f"{existing}\n\n{inferred_block}" if existing else inferred_block
