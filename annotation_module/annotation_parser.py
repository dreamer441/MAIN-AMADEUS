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


@dataclass(frozen=True)
class AnnotationBlock:
    """One independently delimited annotation command found in a message."""

    annotation: ParsedAnnotation
    is_terminated: bool


@dataclass(frozen=True)
class ParsedAnnotationMessage:
    """Parser-owned split between annotation blocks and ordinary prompt text."""

    blocks: list[AnnotationBlock]
    normal_prompt: str
    is_legacy_leading_annotation: bool


class AnnotationParser:
    """Parses legacy leading annotations and independently delimited blocks."""

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

    def parse_message(self, message: str) -> ParsedAnnotationMessage:
        """Extract independent annotation blocks without exposing block syntax to Core.

        A block starts at an annotation bracket, ends at its first `[end]`, and does
        not inspect possible annotations inside its content. Without `[end]`, the
        block consumes the rest of the message. Text removed from completed blocks
        is the only text returned as the normal-chat prompt.
        """
        blocks: list[AnnotationBlock] = []
        normal_parts: list[str] = []
        cursor = 0
        search_index = 0
        block_pattern = re.compile(r"\[([^\[\]]+)\]")
        end_pattern = re.compile(r"\[\s*end\s*\]", re.IGNORECASE)

        while True:
            opening_match = block_pattern.search(message, search_index)
            if opening_match is None:
                break

            if self._normalize_token(opening_match.group(1)) == "end":
                search_index = opening_match.end()
                continue

            end_match = end_pattern.search(message, opening_match.end())
            block_end = end_match.start() if end_match is not None else len(message)
            annotation = self.parse(message[opening_match.start() : block_end])
            if annotation is None:
                search_index = opening_match.end()
                continue

            normal_parts.append(message[cursor : opening_match.start()])
            blocks.append(AnnotationBlock(annotation=annotation, is_terminated=end_match is not None))
            cursor = end_match.end() if end_match is not None else len(message)
            search_index = cursor

            if end_match is None:
                break

        normal_parts.append(message[cursor:])
        normal_prompt = "".join(normal_parts).strip()
        is_legacy_leading_annotation = (
            len(blocks) == 1
            and not blocks[0].is_terminated
            and not message[: message.find("[")].strip()
        )
        return ParsedAnnotationMessage(
            blocks=blocks,
            normal_prompt=normal_prompt,
            is_legacy_leading_annotation=is_legacy_leading_annotation,
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
