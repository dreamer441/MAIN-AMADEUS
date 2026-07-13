"""Focused safety and temporary-context tests for Phase 4 project navigation."""

import tempfile
import unittest
from pathlib import Path

from amadeus_core.core import AmadeusCore
from project_file_reader import ProjectFileReader, UnsafeProjectFileError
from project_file_reader.project_file_reader import MAX_FILE_SIZE_BYTES


class ProjectFileReaderTests(unittest.TestCase):
    """Verify root navigation and guarded reads use the reader as one boundary."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "example.py").write_text("print('ok')\n", encoding="utf-8")
        (self.root / "notes.txt").write_bytes("café".encode("cp1252"))
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("private", encoding="utf-8")
        self.reader = ProjectFileReader(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_tree_and_file_metadata_are_project_root_relative(self) -> None:
        tree = self.reader.list_project_directory()
        self.assertEqual(["src"], [entry.name for entry in tree.folders])
        self.assertEqual(["notes.txt"], [entry.name for entry in tree.files])
        content = self.reader.read_project_file("notes.txt")
        self.assertEqual("café", content.content)
        self.assertEqual("cp1252", content.encoding)
        self.assertEqual("notes.txt", content.relative_path)

    def test_unsafe_paths_binary_and_oversized_files_are_rejected(self) -> None:
        (self.root / "image.bin").write_bytes(b"text\x00binary")
        (self.root / "large.txt").write_bytes(b"a" * (MAX_FILE_SIZE_BYTES + 1))
        for path in ("../outside.txt", ".git/config", "image.bin", "large.txt"):
            with self.subTest(path=path):
                with self.assertRaises(UnsafeProjectFileError):
                    self.reader.read_project_file(path)

    def test_module_reads_delegate_to_the_same_project_root_reader(self) -> None:
        module = self.root / "sample_module"
        module.mkdir()
        for document in ("README.md", "FEATURES.md", "FUTURE_UPDATES.md"):
            (module / document).write_text("# Sample\n", encoding="utf-8")
        (module / "source.py").write_text("answer = 42\n", encoding="utf-8")

        root_content = self.reader.read_project_file("sample_module/source.py")
        module_content = self.reader.read_module_file("sample_module", "source.py")

        self.assertEqual(root_content.content, module_content.content)
        self.assertEqual(root_content.total_characters, module_content.total_characters)


class SelectedFileContextTests(unittest.TestCase):
    """Verify explicit file context is exact, line-labelled, and request-scoped."""

    def test_context_is_line_labelled_and_range_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "selected.py").write_text("first\nsecond\nthird\n", encoding="utf-8")
            reader = ProjectFileReader(root)

            context = reader.build_project_file_context("selected.py", "2-3")

            self.assertIn("Lines: 2-3 of 3", context)
            self.assertIn("2: second\n3: third", context)
            self.assertNotIn("1: first", context)
            for invalid_range in ("0", "3-2", "4", "one", "1-4"):
                with self.subTest(line_range=invalid_range):
                    with self.assertRaises(ValueError):
                        reader.build_project_file_context("selected.py", invalid_range)

    def test_core_uses_file_context_only_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "selected.py").write_text("first\nsecond\n", encoding="utf-8")
            core = object.__new__(AmadeusCore)
            core.file_reader = ProjectFileReader(root)
            received_contexts: list[str | None] = []

            def capture(message: str, callable_context: str | None = None) -> dict[str, str]:
                received_contexts.append(callable_context)
                return {"response": message}

            core.handle_user_message = capture  # type: ignore[method-assign]

            core.ask_about_project_file("selected.py", "visual only", False, "not a range")
            core.ask_about_project_file("selected.py", "explain this", True, "2")

            self.assertEqual([None], received_contexts[:1])
            self.assertIn("2: second", received_contexts[1] or "")


if __name__ == "__main__":
    unittest.main()
