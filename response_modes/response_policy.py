"""Canonical fixed response modes and their non-executing request policies."""

from dataclasses import dataclass
from enum import Enum


class ResponseMode(str, Enum):
    """Canonical modes accepted by persistence, GUI, and request execution."""

    NONE = "none"
    SHORT = "short"
    NORMAL = "normal"
    LARGE = "large"
    FULL_SEND = "full_send"

    @classmethod
    def parse(cls, value: object, default: "ResponseMode | None" = None) -> "ResponseMode":
        """Parse stored and human-facing values without letting arbitrary strings through."""
        fallback = default or cls.NORMAL
        if isinstance(value, cls):
            return value
        if value is None:
            return fallback
        normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "no_response": cls.NONE,
            "silent": cls.NONE,
            "off": cls.NONE,
            "brief": cls.SHORT,
            "small": cls.SHORT,
            "default": cls.NORMAL,
            "medium": cls.NORMAL,
            "long": cls.LARGE,
            "detailed": cls.LARGE,
            "full": cls.FULL_SEND,
            "fullsend": cls.FULL_SEND,
            "unlimited": cls.FULL_SEND,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return cls(normalized)
        except ValueError:
            return fallback


@dataclass(frozen=True, slots=True)
class ResponsePolicy:
    """Immutable behavior contract for one response mode, without request execution."""

    mode: ResponseMode
    reply_required: bool
    target_tokens: int
    hard_limit_tokens: int
    detail_instruction: str
    allow_continuation: bool = False
    completion_review: bool = False
    show_acknowledgement: bool = False

    def to_metadata(self) -> dict[str, object]:
        """Return safe policy facts suitable for Process Monitor metadata."""
        return {
            "mode": self.mode.value,
            "reply_required": self.reply_required,
            "target_tokens": self.target_tokens,
            "hard_limit_tokens": self.hard_limit_tokens,
            "allow_continuation": self.allow_continuation,
            "completion_review": self.completion_review,
            "show_acknowledgement": self.show_acknowledgement,
        }


POLICY_REGISTRY: dict[ResponseMode, ResponsePolicy] = {
    ResponseMode.NONE: ResponsePolicy(ResponseMode.NONE, False, 0, 0, "Perform required internal operations, but do not produce a normal user-facing answer.", show_acknowledgement=True),
    ResponseMode.SHORT: ResponsePolicy(ResponseMode.SHORT, True, 180, 350, "Give the minimum complete answer. Lead with the direct result. Exclude optional background unless it is necessary for correctness or safety."),
    ResponseMode.NORMAL: ResponsePolicy(ResponseMode.NORMAL, True, 700, 1400, "Give a balanced, complete answer with enough explanation to understand and act. Avoid unnecessary expansion.", completion_review=True),
    ResponseMode.LARGE: ResponsePolicy(ResponseMode.LARGE, True, 1800, 3200, "Give a detailed, structured answer. Include rationale, examples, alternatives, risks, and implementation details when relevant. Avoid repetition.", completion_review=True),
    ResponseMode.FULL_SEND: ResponsePolicy(ResponseMode.FULL_SEND, True, 5000, 12000, "Complete the task fully without shortening it to meet a stylistic brevity target. Continue while additional content materially advances the task. Stop when complete or when a technical limit is reached. Avoid repetition.", allow_continuation=True, completion_review=True),
}


@dataclass(frozen=True, slots=True)
class ResponseModeDecision:
    """One request's resolved mode, kept stable after request execution begins."""

    mode: ResponseMode
    policy: ResponsePolicy
    source: str

    def to_metadata(self) -> dict[str, object]:
        """Return safe decision metadata without including prompts or chat content."""
        metadata = self.policy.to_metadata()
        metadata["source"] = self.source
        return metadata


def resolve_response_mode(
    send_override: object = None,
    chat_mode: object = None,
    global_mode: object = None,
) -> ResponseModeDecision:
    """Resolve one request mode in override, chat, global, default order."""
    for source, value in (("send_override", send_override), ("chat_setting", chat_mode), ("global_setting", global_mode)):
        if value is not None:
            mode = ResponseMode.parse(value)
            return ResponseModeDecision(mode, POLICY_REGISTRY[mode], source)
    mode = ResponseMode.NORMAL
    return ResponseModeDecision(mode, POLICY_REGISTRY[mode], "default")
