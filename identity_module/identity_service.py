from dataclasses import dataclass
from pathlib import Path

from identity_module.identity_charter import (
    COMPACT_IDENTITY_LINES,
    IDENTITY_CHARTER_MARKDOWN,
    IDENTITY_CHARTER_TITLE,
    IDENTITY_CHARTER_VERSION,
    PROJECT_IDENTITY_LINES,
)


@dataclass(frozen=True)
class IdentitySnapshot:
    """Read-only snapshot of AMADEUS's current global identity."""

    title: str
    version: str
    charter_markdown: str
    compact_prompt: str
    project_prompt: str


class IdentityService:
    """Loads and formats AMADEUS's global identity.

    Identity stays separate from Chat and Reasoning so future modes can change
    thinking style without deleting AMADEUS's core self-definition.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        # project_root is stored for future editable/versioned identity files.
        self.project_root = project_root

    def load_snapshot(self) -> IdentitySnapshot:
        """Return the current identity snapshot."""
        return IdentitySnapshot(
            title=IDENTITY_CHARTER_TITLE,
            version=IDENTITY_CHARTER_VERSION,
            charter_markdown=IDENTITY_CHARTER_MARKDOWN,
            compact_prompt=self.build_compact_prompt(),
            project_prompt=self.build_project_prompt(),
        )

    def build_compact_prompt(self) -> str:
        """Build the default identity prompt injected into normal chat."""
        return self._format_prompt_block("AMADEUS Global Identity", COMPACT_IDENTITY_LINES)

    def build_project_prompt(self) -> str:
        """Build a stronger identity prompt for AMADEUS project/reasoning chats."""
        return self._format_prompt_block("AMADEUS Project Identity", PROJECT_IDENTITY_LINES)

    def build_status_report(self) -> str:
        """Return a readable identity status summary for the GUI/chat."""
        snapshot = self.load_snapshot()
        return (
            f"{snapshot.title}\n"
            f"Version: {snapshot.version}\n\n"
            "Identity module status: active\n\n"
            "Core rule:\n"
            "Identity is global. Reasoning profiles are temporary. "
            "A reasoning profile may change method, but must not erase identity.\n\n"
            "Available identity commands:\n"
            "* [identity] - show this status\n"
            "* [identity][prompt] - show the compact injected prompt\n"
            "* [identity][project] - show the stronger project prompt\n"
            "* [identity][charter] - show the full charter"
        )

    def _format_prompt_block(self, title: str, lines: tuple[str, ...]) -> str:
        """Format identity lines into a stable prompt section."""
        bullet_lines = "\n".join(f"- {line}" for line in lines)
        return f"{title}:\n{bullet_lines}"
