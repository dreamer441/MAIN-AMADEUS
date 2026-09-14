"""Read-only Git review context for the explicit Flow ``/review`` command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from collections.abc import Callable

from project_file_reader import ProjectFileReader


MAX_CHANGED_FILES = 8
MAX_FILE_CHARACTERS = 4_000
MAX_CHANGED_CHARACTERS = 20_000
MAX_DOCUMENT_CHARACTERS = 8_000


@dataclass(frozen=True, slots=True)
class FlowReviewRequest:
    """A validated explicit Flow patch-review request."""

    question: str

    @classmethod
    def parse(cls, message: str) -> "FlowReviewRequest | None":
        """Parse only the exact ``/review <question>`` command."""
        if not message.startswith("/review"):
            return None
        if len(message) > len("/review") and not message[len("/review")].isspace():
            return None
        question = message[len("/review") :].strip()
        if not question:
            raise ValueError("Use /review followed by a review question.")
        return cls(question)


class FlowReviewContextBuilder:
    """Build bounded, read-only project context for one explicit review request."""

    def __init__(
        self,
        project_root: Path,
        file_reader: ProjectFileReader,
        run_command: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.file_reader = file_reader
        self.run_command = run_command or self._run_command

    def build(self, request: FlowReviewRequest) -> str:
        """Return documentation, Git state, then safe bounded changed-file content."""
        del request
        sections = [
            self._read_document("AMADEUS_CHANGELOG.md", "AMADEUS CHANGELOG"),
            self._read_document("AMADEUS_FUTURE_IMPLEMENTATIONS.md", "AMADEUS FUTURE IMPLEMENTATIONS"),
        ]
        status = self._run_git(["git", "status", "--short"])
        changed = self._run_git(["git", "diff", "--name-only"])
        stat = self._run_git(["git", "diff", "--stat"])
        sections.append(self._format_git_state(status, changed, stat))
        sections.append(self._read_changed_files(status, changed))
        return "\n\n---\n\n".join(sections)

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a read-only Git command from the project root without a shell."""
        return subprocess.run(
            command,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_git(self, command: list[str]) -> str | None:
        """Return Git output or a safe unavailable marker without exposing errors."""
        try:
            result = self.run_command(command)
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout if result.returncode == 0 else None

    def _read_document(self, relative_path: str, label: str) -> str:
        """Read required root documentation through the project-file boundary."""
        try:
            content = self.file_reader.read_project_file(relative_path, max_characters=MAX_DOCUMENT_CHARACTERS)
        except Exception:
            return f"[{label}]\nOmitted: unavailable or unsafe to read."
        suffix = "\n[Document truncated for review context.]" if content.truncated else ""
        return f"[{label}]\n{content.content}{suffix}"

    def _format_git_state(self, status: str | None, changed: str | None, stat: str | None) -> str:
        """Label all requested Git snapshots, including safely handled failures."""
        return "\n".join(
            (
                "[CURRENT GIT STATE]",
                "git status --short:",
                status.rstrip() if status is not None else "Git unavailable or command failed.",
                "git diff --name-only:",
                changed.rstrip() if changed is not None else "Git unavailable or command failed.",
                "git diff --stat:",
                stat.rstrip() if stat is not None else "Git unavailable or command failed.",
            )
        )

    def _read_changed_files(self, status: str | None, changed: str | None) -> str:
        """Read a fixed number of verified changed text files through the reader."""
        paths, omitted_directories = self._changed_paths(status, changed)
        sections = ["[SAFE CHANGED PROJECT FILES]"]
        omitted_ignored = omitted_unreadable = omitted_bounded = 0
        used_characters = 0
        included = 0
        for relative_path in paths:
            target = self._safe_path(relative_path)
            if target is None:
                omitted_ignored += 1
                continue
            if included >= MAX_CHANGED_FILES or used_characters >= MAX_CHANGED_CHARACTERS:
                omitted_bounded += 1
                continue
            try:
                content = self.file_reader.read_project_file(relative_path, max_characters=MAX_FILE_CHARACTERS)
            except Exception:
                omitted_unreadable += 1
                continue
            remaining = MAX_CHANGED_CHARACTERS - used_characters
            if remaining <= 0:
                omitted_bounded += 1
                continue
            text = content.content[:remaining]
            truncated = content.truncated or len(text) < len(content.content)
            sections.append(f"[FILE: {content.relative_path}]\n{text}" + ("\n[File truncated for review context.]" if truncated else ""))
            included += 1
            used_characters += len(text)
        sections.append(
            "Included "
            f"{included} file(s); omitted {omitted_ignored} ignored/unsafe, "
            f"{omitted_unreadable} unreadable/binary/unsupported, and {omitted_bounded} bounded file(s)."
            f" Skipped {omitted_directories} untracked director{'y' if omitted_directories == 1 else 'ies'}."
        )
        return "\n\n".join(sections)

    def _changed_paths(self, status: str | None, changed: str | None) -> tuple[list[str], int]:
        """Combine tracked diff paths with untracked porcelain paths in stable order."""
        paths: list[str] = []
        omitted_directories = 0
        for line in (changed or "").splitlines():
            if line.strip():
                paths.append(line.strip())
        for line in (status or "").splitlines():
            if not line.startswith("?? "):
                continue
            path = line[3:].strip()
            target = self._safe_path(path)
            if target is not None and target.is_dir():
                omitted_directories += 1
            elif path:
                paths.append(path)
        return list(dict.fromkeys(paths)), omitted_directories

    def _safe_path(self, relative_path: str) -> Path | None:
        """Reject Git paths outside the project before consulting the file reader."""
        try:
            target = (self.project_root / relative_path).resolve()
            target.relative_to(self.project_root)
        except (OSError, ValueError):
            return None
        return target
