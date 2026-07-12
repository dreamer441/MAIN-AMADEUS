"""Deterministic natural-language routing for simple project file questions.

The normal LLM is useful for explanation, but it is not reliable as a filesystem
source. This router catches explicit inspection requests such as:

    "open identity module and list all files"
    "give me the exact first line of identity_charter.py"
    "how many lines are in identity_charter.py"

and returns a direct answer from ProjectFileReader. If the router cannot identify
an exact file/folder task, it returns None and Core continues to normal chat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from project_file_reader.project_file_reader import (
    ModuleFileContent,
    ModuleFileLine,
    ModuleFileLineCount,
    ModuleFileListing,
    ProjectFileNotFoundError,
    ProjectFileReader,
    ProjectModuleNotFoundError,
    UnsafeProjectFileError,
)


LISTING_WORDS = (
    "list",
    "show",
    "open",
    "see",
    "check",
    "inspect",
    "what files",
    "which files",
    "file titles",
    "titles of all files",
)

FILE_SCOPE_WORDS = (
    "file",
    "files",
    "folder",
    "directory",
    "module",
    "included",
    "contains",
)

READ_WORDS = (
    "read",
    "open",
    "show content",
    "show contents",
    "display",
)

LINE_COUNT_WORDS = (
    "number of lines",
    "line count",
    "count lines",
    "how many lines",
    "total lines",
)

ORDINAL_LINE_WORDS = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
}

SUPPORTED_TEXT_FILE_RE = r"[A-Za-z0-9_./\-]+\.(?:py|md|txt|json|toml|yaml|yml|ini|cfg)"


@dataclass(frozen=True)
class FileRequestResult:
    """Result returned when a message was handled as a real file request."""

    response: str
    action: str
    module_name: str | None = None


class FileRequestRouter:
    """Handles obvious local project file requests without using the LLM.

    This router is intentionally narrow. When it sees a request for a file list,
    full file content, one exact line, or an exact line count, it bypasses the LLM
    and returns filesystem data directly. This prevents AMADEUS from sounding
    confident while actually guessing file contents.
    """

    def __init__(self, file_reader: ProjectFileReader) -> None:
        self.file_reader = file_reader

    def try_handle(self, message: str) -> FileRequestResult | None:
        """Return a deterministic file response, or None for normal chat routing."""
        clean_message = " ".join(message.strip().split())
        if not clean_message:
            return None

        lowered_message = clean_message.lower()
        file_name = self._extract_requested_file_name(clean_message)
        module_name = self._detect_module_name(clean_message)

        if module_name is None and file_name:
            # Follow-up questions often mention only the file name because the module
            # was discussed one turn earlier. We still avoid guessing: the router may
            # infer the module only if exactly one readable module contains that file.
            module_result = self._detect_single_module_containing_file(file_name)
            if isinstance(module_result, FileRequestResult):
                return module_result
            module_name = module_result

        if module_name is None:
            if file_name and self._looks_like_any_specific_file_request(lowered_message):
                return FileRequestResult(
                    response=(
                        f"I could not verify a readable AMADEUS module containing `{file_name}`.\n\n"
                        "I will not guess file contents or line counts without a verified local file."
                    ),
                    action="file_not_found",
                    module_name=None,
                )
            return None

        # Specific line/line-count requests must be checked before full-file reads.
        # Example: "give me the first line of identity_charter.py" contains a file
        # name, but the correct answer is one line, not the whole file or an LLM answer.
        if file_name and self._looks_like_line_count_request(lowered_message):
            return self._count_file_lines(module_name, file_name)

        if file_name and self._looks_like_line_read_request(lowered_message):
            line_number = self._extract_requested_line_number(lowered_message)
            if line_number is not None:
                return self._read_one_file_line(module_name, file_name, line_number)

        if file_name and self._looks_like_file_read_request(lowered_message):
            return self._read_one_file(module_name, file_name)

        if self._looks_like_file_listing_request(lowered_message):
            return self._list_module_files(module_name)

        return None

    def _detect_module_name(self, message: str) -> str | None:
        """Detect which known module the user mentioned.

        Module names are compared using both snake_case and space-separated forms,
        so "identity module" maps to the real `identity_module` folder.
        """
        lowered_message = message.lower()
        normalized_message = self.file_reader.normalize_module_name(message)
        modules = self.file_reader.list_module_names()

        # Prefer longer names first so `amadeus_trace` wins over a shorter partial match later.
        for module_name in sorted(modules, key=len, reverse=True):
            normalized_module = self.file_reader.normalize_module_name(module_name)
            spaced_module = normalized_module.replace("_", " ")
            compact_module = normalized_module.replace("_", "")

            if module_name.lower() in lowered_message:
                return module_name
            if spaced_module in lowered_message:
                return module_name
            if normalized_module in normalized_message:
                return module_name
            if compact_module and compact_module in normalized_message.replace("_", ""):
                return module_name

        return None

    def _detect_single_module_containing_file(self, file_name: str) -> str | FileRequestResult | None:
        """Find the owning module for a uniquely named direct module file.

        This supports natural follow-ups like “what is the first line of
        identity_charter.py?” after the user was already talking about
        `identity_module`. We only infer the module when the filename exists in
        exactly one readable module. Multiple matches produce an honest ambiguity
        message instead of choosing randomly.
        """
        normalized_file_name = file_name.strip().strip('"').strip("'").lower()
        matches: list[str] = []

        for candidate_module in self.file_reader.list_module_names():
            try:
                listing = self.file_reader.list_module_files(candidate_module)
            except ProjectModuleNotFoundError:
                continue

            for entry in listing.files:
                if entry.relative_path.lower() == normalized_file_name or entry.name.lower() == normalized_file_name:
                    matches.append(candidate_module)
                    break

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            options = "\n".join(f"* `{module_name}/{file_name}`" for module_name in matches)
            return FileRequestResult(
                response=(
                    f"I found more than one verified file named `{file_name}`.\n\n"
                    "Please specify which module/file path you mean:\n"
                    f"{options}"
                ),
                action="ambiguous_file_request",
                module_name=None,
            )

        return None

    def _looks_like_any_specific_file_request(self, lowered_message: str) -> bool:
        """Return True when the message asks for a concrete file fact.

        Used when a filename is present but no module can be verified. In that
        case, Core should return an honest no-file result instead of sending the
        question to the LLM where it may hallucinate.
        """
        return (
            self._looks_like_file_read_request(lowered_message)
            or self._looks_like_line_read_request(lowered_message)
            or self._looks_like_line_count_request(lowered_message)
        )

    def _looks_like_file_listing_request(self, lowered_message: str) -> bool:
        """Return True for messages asking for exact folder/module file names."""
        has_listing_word = any(word in lowered_message for word in LISTING_WORDS)
        has_file_scope = any(word in lowered_message for word in FILE_SCOPE_WORDS)
        return has_listing_word and has_file_scope

    def _looks_like_file_read_request(self, lowered_message: str) -> bool:
        """Return True when the user names a concrete file and asks to read/open it."""
        has_read_word = any(word in lowered_message for word in READ_WORDS)
        has_file_extension = re.search(rf"\b{SUPPORTED_TEXT_FILE_RE}\b", lowered_message)
        return has_read_word and has_file_extension is not None

    def _looks_like_line_count_request(self, lowered_message: str) -> bool:
        """Return True when the request asks for an exact number of lines."""
        return any(phrase in lowered_message for phrase in LINE_COUNT_WORDS)

    def _looks_like_line_read_request(self, lowered_message: str) -> bool:
        """Return True when the request asks for a specific line from a file."""
        if "line" not in lowered_message:
            return False
        if any(phrase in lowered_message for phrase in LINE_COUNT_WORDS):
            return False

        # Accept common human phrasing like "first line", "line 1", or "1st line".
        if any(f"{word} line" in lowered_message for word in ORDINAL_LINE_WORDS):
            return True
        if re.search(r"\bline\s+\d+\b", lowered_message):
            return True
        if re.search(r"\b\d+(?:st|nd|rd|th)?\s+line\b", lowered_message):
            return True
        return False

    def _extract_requested_file_name(self, message: str) -> str | None:
        """Extract a safe filename from a natural-language message.

        This parser only accepts names with approved text extensions. If no exact
        file name is present, the router refuses to guess.
        """
        match = re.search(rf"\b({SUPPORTED_TEXT_FILE_RE})\b", message, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).rstrip("`.,;:)")

    def _extract_requested_line_number(self, lowered_message: str) -> int | None:
        """Extract a 1-based line number from common phrasing."""
        for word, number in ORDINAL_LINE_WORDS.items():
            if f"{word} line" in lowered_message:
                return number

        line_after_number = re.search(r"\bline\s+(\d+)\b", lowered_message)
        if line_after_number:
            return int(line_after_number.group(1))

        number_before_line = re.search(r"\b(\d+)(?:st|nd|rd|th)?\s+line\b", lowered_message)
        if number_before_line:
            return int(number_before_line.group(1))

        return None

    def _list_module_files(self, module_name: str) -> FileRequestResult:
        """Return a direct exact file listing for one module folder."""
        try:
            listing = self.file_reader.list_module_files(module_name)
        except ProjectModuleNotFoundError as error:
            return FileRequestResult(
                response=self._module_not_found_response(error),
                action="module_not_found",
                module_name=None,
            )

        return FileRequestResult(
            response=self._format_file_listing(listing),
            action="list_files",
            module_name=listing.module_name,
        )

    def _read_one_file(self, module_name: str, file_name: str) -> FileRequestResult:
        """Return direct text content for one exact module file."""
        try:
            content = self.file_reader.read_module_file(module_name, file_name)
        except ProjectModuleNotFoundError as error:
            return FileRequestResult(
                response=self._module_not_found_response(error),
                action="module_not_found",
                module_name=None,
            )
        except ProjectFileNotFoundError as error:
            return self._file_not_found_result(module_name, error)
        except UnsafeProjectFileError as error:
            return FileRequestResult(
                response=f"I cannot read that file safely: {error}",
                action="unsafe_file_request",
                module_name=module_name,
            )

        return FileRequestResult(
            response=self._format_file_content(content),
            action="read_file",
            module_name=content.module_name,
        )

    def _read_one_file_line(self, module_name: str, file_name: str, line_number: int) -> FileRequestResult:
        """Return one exact source line without involving the LLM."""
        try:
            file_line = self.file_reader.read_module_file_line(module_name, file_name, line_number)
        except ProjectModuleNotFoundError as error:
            return FileRequestResult(
                response=self._module_not_found_response(error),
                action="module_not_found",
                module_name=None,
            )
        except ProjectFileNotFoundError as error:
            return self._file_not_found_result(module_name, error)
        except UnsafeProjectFileError as error:
            return FileRequestResult(
                response=f"I cannot read that file safely: {error}",
                action="unsafe_file_request",
                module_name=module_name,
            )

        return FileRequestResult(
            response=self._format_file_line(file_line),
            action="read_file_line",
            module_name=file_line.module_name,
        )

    def _count_file_lines(self, module_name: str, file_name: str) -> FileRequestResult:
        """Return an exact line count without involving the LLM."""
        try:
            line_count = self.file_reader.count_module_file_lines(module_name, file_name)
        except ProjectModuleNotFoundError as error:
            return FileRequestResult(
                response=self._module_not_found_response(error),
                action="module_not_found",
                module_name=None,
            )
        except ProjectFileNotFoundError as error:
            return self._file_not_found_result(module_name, error)
        except UnsafeProjectFileError as error:
            return FileRequestResult(
                response=f"I cannot read that file safely: {error}",
                action="unsafe_file_request",
                module_name=module_name,
            )

        return FileRequestResult(
            response=self._format_line_count(line_count),
            action="count_file_lines",
            module_name=line_count.module_name,
        )

    def _file_not_found_result(self, module_name: str, error: ProjectFileNotFoundError) -> FileRequestResult:
        """Return a no-guessing file error shared by all file read operations."""
        available = "\n".join(f"* `{name}`" for name in error.available_files) or "No files found."
        return FileRequestResult(
            response=(
                f"I could not verify `{error.requested_file}` in `{module_name}`.\n\n"
                "I will not guess. Exact direct files/details I can verify are:\n"
                f"{available}"
            ),
            action="file_not_found",
            module_name=module_name,
        )

    def _format_file_listing(self, listing: ModuleFileListing) -> str:
        """Format exact file names with a count so mistakes are easier to spot."""
        if not listing.files:
            return f"Module: `{listing.module_name}`\n\nExact direct files found: 0"

        lines = [
            f"Module: `{listing.module_name}`",
            "",
            f"Exact direct files found: {listing.file_count}",
            "",
        ]
        for index, entry in enumerate(listing.files, start=1):
            lines.append(f"{index}. `{entry.relative_path}`")

        lines.extend(
            [
                "",
                "This list is based on the real local filesystem result. I did not include guessed files.",
            ]
        )
        return "\n".join(lines)

    def _format_file_content(self, content: ModuleFileContent) -> str:
        """Format exact file text while clearly marking truncation if it happened."""
        header = (
            f"Module: `{content.module_name}`\n"
            f"File: `{content.relative_path}`\n"
            f"Characters read: {len(content.content)} of {content.total_characters}"
        )
        truncation_note = "\n\nNote: output was truncated for safety." if content.truncated else ""
        return f"{header}{truncation_note}\n\n```text\n{content.content}\n```"

    def _format_file_line(self, file_line: ModuleFileLine) -> str:
        """Format one exact verified line in a way that is easy to compare."""
        return (
            f"Module: `{file_line.module_name}`\n"
            f"File: `{file_line.relative_path}`\n"
            f"Exact line: {file_line.line_number} of {file_line.total_lines}\n\n"
            "```text\n"
            f"{file_line.line_text}\n"
            "```\n\n"
            "This line was read directly from the local filesystem. I did not guess it."
        )

    def _format_line_count(self, line_count: ModuleFileLineCount) -> str:
        """Format an exact verified line count."""
        return (
            f"Module: `{line_count.module_name}`\n"
            f"File: `{line_count.relative_path}`\n\n"
            f"Exact line count: {line_count.total_lines}\n\n"
            "This count was computed from the local file using Python. I did not estimate it."
        )

    def _module_not_found_response(self, error: ProjectModuleNotFoundError) -> str:
        """Return a no-guessing module error with exact available suggestions."""
        if error.suggestions:
            suggestions = "\n".join(f"* `{module_name}`" for module_name in error.suggestions)
            return (
                f"I could not verify a module folder named `{error.requested_name}`.\n\n"
                "Closest verified modules are:\n"
                f"{suggestions}"
            )
        return f"I could not verify a module folder named `{error.requested_name}`. I will not guess."
