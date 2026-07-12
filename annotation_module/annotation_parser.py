"""Parser for AMADEUS bracket annotations.

Annotations are command-like message prefixes such as `[file]` or
`[identity][charter]`. They are parsed before normal chat so Core can route them
into deterministic modules instead of asking the LLM to guess what the user meant.

Important design choice:
- The annotation name is normalized because routing needs stable keys like `file`.
- The annotation arguments are preserved as typed because file paths need dots,
  slashes, capitalization, and spaces. Older versions normalized every argument,
  which turned `core.py` into `core_py` and made exact file access fragile.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedAnnotation:
    """Structured annotation parsed from the start of a user message."""

    annotation_name: str
    arguments: list[str]
    content: str
    normalized_arguments: list[str] = field(default_factory=list)


class AnnotationParser:
    """Parses leading bracket annotations such as `[file][amadeus_core]`."""

    def parse(self, message: str) -> ParsedAnnotation | None:
        """Return a parsed annotation, or None when the message is normal chat.

        Only bracket blocks at the very beginning are treated as annotation syntax.
        Everything after those leading blocks becomes normal annotation content.
        """
        stripped_message = message.lstrip()
        if not stripped_message.startswith("["):
            return None

        parts: list[str] = []
        index = 0

        # Parse only consecutive leading bracket blocks. This allows content after
        # the command, for example: `[file][core] explain why this module exists`.
        while index < len(stripped_message) and stripped_message[index] == "[":
            closing_index = stripped_message.find("]", index + 1)
            if closing_index == -1:
                return None

            raw_part = stripped_message[index + 1 : closing_index].strip()
            if not raw_part:
                return None

            parts.append(raw_part)
            index = closing_index + 1

            # Spaces are allowed between bracket blocks, so `[file] [core.py]`
            # still parses as a single annotation command.
            next_non_space = self._next_non_space_index(stripped_message, index)
            if next_non_space is None or stripped_message[next_non_space] != "[":
                break

            index = next_non_space

        if not parts:
            return None

        raw_arguments = [part.strip() for part in parts[1:]]
        return ParsedAnnotation(
            annotation_name=self._normalize_token(parts[0]),
            arguments=raw_arguments,
            normalized_arguments=[self._normalize_token(part) for part in raw_arguments],
            content=stripped_message[index:].strip(),
        )

    def normalize_token(self, token: str) -> str:
        """Public helper for handlers that need the same token normalization."""
        return self._normalize_token(token)

    def _normalize_token(self, token: str) -> str:
        """Normalize annotation names into snake_case identifiers."""
        normalized = token.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")

    def _next_non_space_index(self, text: str, start_index: int) -> int | None:
        """Return the next non-space index after a parsed bracket block."""
        for index in range(start_index, len(text)):
            if not text[index].isspace():
                return index
        return None
