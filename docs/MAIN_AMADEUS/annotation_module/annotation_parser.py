import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedAnnotation:
    """Structured annotation parsed from the start of a user message."""

    annotation_name: str
    arguments: list[str]
    content: str


class AnnotationParser:
    """Parses leading bracket annotations such as `[file][amadeus_core]`."""

    def parse(self, message: str) -> ParsedAnnotation | None:
        """Return a parsed annotation, or None when the message is normal chat."""
        stripped_message = message.lstrip()
        if not stripped_message.startswith("["):
            return None

        parts: list[str] = []
        index = 0

        # Only leading bracket blocks are annotation syntax. Remaining text is content.
        while index < len(stripped_message) and stripped_message[index] == "[":
            closing_index = stripped_message.find("]", index + 1)
            if closing_index == -1:
                return None

            raw_part = stripped_message[index + 1 : closing_index].strip()
            if not raw_part:
                return None

            parts.append(raw_part)
            index = closing_index + 1

            next_non_space = self._next_non_space_index(stripped_message, index)
            if next_non_space is None or stripped_message[next_non_space] != "[":
                break

            index = next_non_space

        if not parts:
            return None

        return ParsedAnnotation(
            annotation_name=self._normalize_token(parts[0]),
            arguments=[self._normalize_token(part) for part in parts[1:]],
            content=stripped_message[index:].strip(),
        )

    def _normalize_token(self, token: str) -> str:
        """Normalize annotation names and arguments into snake_case identifiers."""
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
