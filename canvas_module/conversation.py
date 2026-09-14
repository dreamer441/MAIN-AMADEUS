"""Canvas-to-AMADEUS request execution through the shared LLM boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from amadeus_trace import TraceLogger
from canvas_module.canvas_module import CanvasModule
from canvas_module.context import CanvasContextPackage
from canvas_module.models import CanvasConnector, CanvasSendOperation, CanvasTextBlock
from llm_client import OllamaClient, OllamaClientError


CANVAS_MODEL_PROFILES = {
    "light": "qwen3:4b",
    "normal": "qwen3:14b",
    "heavy": "qwen3:32b",
}
DEFAULT_CANVAS_MODEL_WEIGHT = "normal"

CANVAS_SYSTEM_PROMPT = """
You are AMADEUS replying inside the AMADEUS Infinite Canvas.
Answer the actual text or request in every response target immediately.
There may be several selected or changed target blocks; handle all of them together in one coherent response and do not silently ignore one.
Use every relevant arrow-connected earlier block to understand how each target was reached.
Use plain-line neighbours only as related background.
When comparing or combining ideas, inspect all connected source blocks and do not invent a shared fact that their content does not support. If the supplied blocks do not establish a commonality, say that plainly; label any additional comparison drawn from general knowledge.
Do not explain the Canvas structure, context assembly, object roles, connector mechanics, or internal processing.
Do not mention object IDs, connector IDs, response targets, related peers, ancestors, descendants, JSON, metadata, or prompts.
Do not begin with phrases such as "The user asked", "I can see", "To answer this", or "I will".
Do not restate the request unless clarification is necessary.
Do not add generic offers such as "Would you like more?" unless Dato asks for options.
Use only the length needed for a useful answer, normally one to three short paragraphs.
For an exact value, code, name, or definition, give that answer first and directly.
Return only the text that should appear inside one AMADEUS Canvas block.
""".strip()


_INTERNAL_RESPONSE_MARKERS = (
    "canvas_text_",
    "canvas_connector_",
    "response_target",
    "related_peer",
    "directional_ancestor",
    "directional_descendant",
    "structured canvas context",
    "target object",
    "parent connector",
)

_META_OPENERS = (
    "the user has asked",
    "the user asked",
    "i can see that",
    "to answer this",
    "i will describe",
    "the target object",
)


class CanvasLLMClient(Protocol):
    """Minimal generation boundary used by Canvas conversation execution."""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate one response for the prepared Canvas request."""


@dataclass(frozen=True, slots=True)
class CanvasExecutionResult:
    """Outcome of one Canvas request, including newly committed scene objects."""

    response: str | None = None
    response_block: CanvasTextBlock | None = None
    response_connector: CanvasConnector | None = None
    send_operation: CanvasSendOperation | None = None
    context_package: CanvasContextPackage | None = None
    error: Exception | None = None

    @property
    def succeeded(self) -> bool:
        return (
            self.error is None
            and self.response is not None
            and self.response_block is not None
            and self.send_operation is not None
        )


class CanvasConversationService:
    """Build Canvas context, call the configured LLM, and commit atomically."""

    def __init__(self, canvas_module: CanvasModule, llm_client: CanvasLLMClient) -> None:
        self.canvas_module = canvas_module
        self.llm_client = llm_client

    def handle_request(
        self,
        *,
        instruction: str = "",
        context_mode: str = "viewport",
        visible_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_connector_ids: list[str] | tuple[str, ...] | set[str] = (),
        branch_root_id: str | None = None,
        identity_prompt: str | None = None,
        trace_logger: TraceLogger | None = None,
        process_run_id: str = "",
        model_weight: str = DEFAULT_CANVAS_MODEL_WEIGHT,
    ) -> CanvasExecutionResult:
        """Execute a target-focused Canvas request without mutating on failure."""

        try:
            self._trace(
                trace_logger,
                "module",
                "Canvas Context Build Started",
                "Collecting changed targets and eligible graph-connected support from the Canvas.",
            )
            package = self.canvas_module.build_context_preview(
                context_mode=context_mode,
                visible_object_ids=visible_object_ids,
                selected_object_ids=selected_object_ids,
                selected_connector_ids=selected_connector_ids,
                branch_root_id=branch_root_id,
            )
            if not self._has_response_target(package):
                raise ValueError(
                    "Canvas has no response target. Add or edit a block, or select the block AMADEUS should answer."
                )
            self._trace(
                trace_logger,
                "module",
                "Canvas Context Prepared",
                "Canvas response targets and supporting graph context were prepared.",
                level="success",
            )
            prompt = self.build_prompt(package, instruction)
            system_prompt = self._build_system_prompt(identity_prompt)
            self._trace(
                trace_logger,
                "llm",
                "Canvas Request Sent",
                "Sending the prepared Canvas request to the configured LLM.",
            )
            selected_client, selected_model = self._client_for_weight(model_weight)
            self._validate_selected_model(selected_client, selected_model)
            self._trace(
                trace_logger,
                "llm",
                "Canvas Model Ready",
                f"Generating the Canvas response with {selected_model}.",
            )
            response = selected_client.generate(prompt=prompt, system_prompt=system_prompt)
            if not isinstance(response, str) or not response.strip():
                raise ValueError("Configured LLM returned an empty Canvas response")

            # Small local models can occasionally answer the old machine-readable
            # metadata instead of Dato's text. One focused retry is cheaper and
            # safer than committing a useless Canvas block.
            if self._looks_like_internal_meta_response(response):
                self._trace(
                    trace_logger,
                    "llm",
                    "Canvas Response Correction Requested",
                    "The first response described Canvas internals instead of answering the target; retrying once.",
                )
                response = selected_client.generate(
                    prompt=self._build_correction_prompt(prompt, response),
                    system_prompt=system_prompt,
                )
                if not isinstance(response, str) or not response.strip():
                    raise ValueError("Configured LLM returned an empty Canvas response after correction")
                if self._looks_like_internal_meta_response(response):
                    raise ValueError(
                        "AMADEUS described Canvas metadata instead of answering the selected content. "
                        "No response block was created."
                    )

            response = response.strip()
            self._trace(
                trace_logger,
                "llm",
                "Canvas Response Received",
                "Configured LLM returned a direct response for the Canvas.",
                level="success",
            )
            response_block, response_connector, operation = self.canvas_module.commit_amadeus_response(
                context_package=package,
                response_text=response,
                instruction=instruction,
                process_run_id=process_run_id,
                model_name=selected_model,
                prompt_text=prompt,
            )
            self._trace(
                trace_logger,
                "output",
                "Canvas Response Stored",
                "AMADEUS response block, source link, send record, and semantic baseline were saved atomically.",
                level="success",
            )
            return CanvasExecutionResult(
                response=response,
                response_block=response_block,
                response_connector=response_connector,
                send_operation=operation,
                context_package=package,
            )
        except (OllamaClientError, RuntimeError, ValueError) as error:
            self._trace(
                trace_logger,
                "error",
                "Canvas Request Failed",
                "Canvas request could not be completed or committed safely.",
                level="error",
            )
            return CanvasExecutionResult(error=error)

    def _client_for_weight(self, model_weight: str) -> tuple[CanvasLLMClient, str]:
        """Return a Canvas-specific Ollama client for the selected weight.

        Injected fake/test clients remain untouched. Real Ollama clients are
        cloned with the selected model so changing Canvas weight never mutates
        Flow Chat or another concurrent module request.
        """

        clean_weight = model_weight.strip().lower() or DEFAULT_CANVAS_MODEL_WEIGHT
        if clean_weight not in CANVAS_MODEL_PROFILES:
            raise ValueError(f"Unsupported Canvas model weight: {clean_weight}")
        requested_model = CANVAS_MODEL_PROFILES[clean_weight]
        if isinstance(self.llm_client, OllamaClient):
            return (
                OllamaClient(
                    model=requested_model,
                    host=self.llm_client.host,
                    timeout_seconds=self.llm_client.timeout_seconds,
                    think=False,
                ),
                requested_model,
            )
        fallback_name = str(getattr(self.llm_client, "model", type(self.llm_client).__name__))
        return self.llm_client, fallback_name


    @staticmethod
    def _validate_selected_model(client: CanvasLLMClient, model_name: str) -> None:
        """Fail visibly before generation when a selected Ollama model is absent."""

        if not isinstance(client, OllamaClient):
            return
        status = client.health_check()
        if not bool(status.get("model_available")):
            available = status.get("available_models", [])
            available_text = ", ".join(str(item) for item in available) or "none"
            raise ValueError(
                f"Canvas model '{model_name}' is not installed. Run `ollama pull {model_name}`. "
                f"Available local models: {available_text}."
            )

    @staticmethod
    def build_prompt(package: CanvasContextPackage, instruction: str = "") -> str:
        """Render semantic Canvas context as human-readable content, not raw JSON.

        Keeping IDs and implementation roles out of the model-facing prompt stops
        small local models from narrating the context machinery instead of
        answering Dato's target block.
        """

        blocks = {block.object_id: block for block in package.objects}
        connectors = {connector.connector_id: connector for connector in package.connectors}
        clean_instruction = instruction.strip()

        def block_text(object_id: str) -> str:
            block = blocks.get(object_id)
            if block is None:
                return ""
            parts: list[str] = []
            if block.title:
                parts.append(f"Title: {block.title}")
            parts.append(block.text.strip())
            if block.comment:
                parts.append(f"Attached comment: {block.comment}")
            return "\n".join(part for part in parts if part)

        def render_blocks(
            title: str,
            object_ids: tuple[str, ...],
            *,
            numbered: bool = False,
        ) -> list[str]:
            texts = [block_text(object_id) for object_id in object_ids]
            texts = [text for text in texts if text]
            if not texts:
                return []
            lines = [title]
            if numbered:
                lines.extend(f"{index}. {text}" for index, text in enumerate(texts, start=1))
            else:
                lines.extend(f"- {text}" for text in texts)
            return lines

        sections: list[str] = [
            "TASK",
            clean_instruction
            or "Reply directly and naturally to the new or edited Canvas content below.",
            "",
        ]
        sections.extend(
            render_blocks(
                "CONTENT TO ANSWER — HANDLE EVERY ITEM",
                package.target_object_ids,
                numbered=True,
            )
        )

        target_relations: list[str] = []
        for connector_id in package.target_connector_ids:
            connector = connectors.get(connector_id)
            if connector is None:
                continue
            source_text = block_text(connector.source_object_id)
            target_text = block_text(connector.target_object_id)
            if not source_text or not target_text:
                continue
            arrow = "→" if connector.connector_type == "arrow" else "—"
            relation = connector.label or connector.relation_type.replace("_", " ")
            target_relations.append(f'- "{source_text}" {arrow} "{target_text}" ({relation})')
        if target_relations:
            sections.extend(["", "NEW OR EDITED RELATIONSHIPS", *target_relations])

        # Preserve graph meaning in the model-facing prompt. This is especially
        # important when several source blocks converge on one question: the
        # model should see that all of those blocks feed the target instead of
        # receiving an unordered bag of ancestor text.
        connection_flow: list[str] = []
        seen_relations: set[tuple[str, str, str, str]] = set()
        for connector in package.connectors:
            source_text = block_text(connector.source_object_id)
            target_text = block_text(connector.target_object_id)
            if not source_text or not target_text:
                continue
            relation_key = (
                connector.connector_type,
                connector.source_object_id,
                connector.target_object_id,
                connector.relation_type,
            )
            if relation_key in seen_relations:
                continue
            seen_relations.add(relation_key)
            symbol = "→" if connector.connector_type == "arrow" else "—"
            relation = connector.label or connector.relation_type.replace("_", " ")
            connection_flow.append(
                f'- "{source_text}" {symbol} "{target_text}" ({relation})'
            )
        if connection_flow:
            sections.extend(["", "CONNECTION FLOW BETWEEN INCLUDED IDEAS", *connection_flow])

        for title, object_ids in (
            ("EARLIER IDEAS LEADING TO THE TARGET", package.ancestor_object_ids),
            ("EXISTING FOLLOW-UP IDEAS", package.descendant_object_ids),
            ("RELATED PEER IDEAS", package.peer_object_ids),
        ):
            rendered = render_blocks(title, object_ids)
            if rendered:
                sections.extend(["", *rendered])

        if package.deleted_object_ids or package.deleted_connector_ids:
            sections.extend(
                [
                    "",
                    "RECENT REMOVAL",
                    "Some previously sent Canvas content or relationship was removed. "
                    "Consider that change only when it affects the task.",
                ]
            )

        sections.extend(
            [
                "",
                "RESPONSE REQUIREMENTS",
                "- Start with the actual answer; do not describe the Canvas or your reasoning process.",
                "- If several target blocks are listed, answer every one of them in the same response.",
                "- Use all relevant connected source blocks; do not choose only the first one.",
                "- For comparisons, if the supplied blocks do not establish a commonality, say so instead of inventing one; clearly label any additional general-knowledge comparison.",
                "- Do not mention internal IDs, context roles, connectors, metadata, or prompt structure.",
                "- Do not restate the request unless clarification is essential.",
                "- Keep the answer focused and concise unless the request clearly needs detail.",
                "- Do not end with a generic offer for more options.",
            ]
        )
        return "\n".join(sections).strip()

    @staticmethod
    def _build_system_prompt(identity_prompt: str | None) -> str:
        if not identity_prompt:
            return CANVAS_SYSTEM_PROMPT
        return f"{CANVAS_SYSTEM_PROMPT}\n\n{identity_prompt.strip()}"

    @staticmethod
    def _looks_like_internal_meta_response(response: str) -> bool:
        normalized = " ".join(response.lower().split())
        if any(marker in normalized for marker in _INTERNAL_RESPONSE_MARKERS):
            return True
        return any(normalized.startswith(opener) for opener in _META_OPENERS)

    @staticmethod
    def _build_correction_prompt(original_prompt: str, unsuitable_response: str) -> str:
        excerpt = unsuitable_response.strip()[:1200]
        return (
            f"{original_prompt}\n\n"
            "CORRECTION\n"
            "Your previous draft discussed the Canvas/context machinery instead of answering the content. "
            "Rewrite it now as only the direct useful answer. Do not mention the Canvas, roles, IDs, connectors, "
            "metadata, or what you are going to do.\n\n"
            f"UNSUITABLE DRAFT\n{excerpt}"
        )

    @staticmethod
    def _has_response_target(package: CanvasContextPackage) -> bool:
        return bool(
            package.target_object_ids
            or package.target_connector_ids
            or package.deleted_object_ids
            or package.deleted_connector_ids
        )

    @staticmethod
    def _trace(
        trace_logger: TraceLogger | None,
        category: str,
        title: str,
        message: str,
        level: str = "info",
    ) -> None:
        if trace_logger is not None:
            trace_logger.add_event(category, title, message, level)
