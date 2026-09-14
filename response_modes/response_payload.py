"""Format response policy and real execution events for presentation."""

from __future__ import annotations

from typing import Any
from amadeus_trace import TraceLogger
from response_modes import ResponseMode, ResponseModeDecision


class ResponsePresenter:
    """Format response policy and real execution events for presentation."""

    def build_response_payload(
        self,
        response: str,
        trace_logger: TraceLogger,
        side_panel: dict[str, Any] | None = None,
        response_decision: ResponseModeDecision | None = None,
        created_chat: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send both chat output and real execution trace back to the GUI."""
        # The GUI uses text fields today, but trace_events is already structured for future filters/export.
        trace_logger.finalize_if_active(title="Response Returned", summary="Response returned to GUI.")
        generated_token_estimate = (len(response) + 3) // 4 if response else 0
        limit_reached = bool(
            response_decision
            and response_decision.policy.hard_limit_tokens > 0
            and generated_token_estimate >= response_decision.policy.hard_limit_tokens
        )
        completion = {
            "mode": response_decision.mode.value if response_decision else ResponseMode.NORMAL.value,
            "generated_token_estimate": generated_token_estimate,
            "limit_reached": limit_reached,
            "complete": not limit_reached,
            "continuation_available": bool(response_decision and response_decision.policy.allow_continuation and limit_reached),
        }
        return {
            # NONE may retain internal backend output for lifecycle accounting, never for UI delivery.
            "response": "" if response_decision and not response_decision.policy.reply_required else response,
            "trace": trace_logger.get_trace_text(mode="compact"),
            "trace_detailed": trace_logger.get_trace_text(mode="detailed"),
            "trace_events": trace_logger.get_trace_events(),
            "side_panel": side_panel,
            "suppress_visible_output": bool(response_decision and not response_decision.policy.reply_required),
            "response_mode": completion["mode"],
            "response_completion": completion,
            "created_chat": created_chat,
        }
