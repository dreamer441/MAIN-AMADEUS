"""Focused safety and temporary-context tests for Phase 4 project navigation."""

import tempfile
import unittest
from pathlib import Path

from project_file_reader.workspace import ProjectFileWorkspace
from project_file_reader import (
    ProjectFileNotFoundError,
    ProjectFileReader,
    ProjectModuleNotFoundError,
    UnsafeProjectFileError,
)
from project_file_reader.project_file_reader import MAX_FILE_SIZE_BYTES
from annotation_module.annotations.metadata_annotation import MetadataAnnotation


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

    def _create_module(self, name: str, features: str, future: str) -> Path:
        """Create one documented module folder for metadata-reader tests."""
        module = self.root / name
        module.mkdir()
        (module / "README.md").write_text("# Module\n", encoding="utf-8")
        (module / "FEATURES.md").write_text(features, encoding="utf-8")
        (module / "FUTURE_UPDATES.md").write_text(future, encoding="utf-8")
        return module

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

    def test_reads_only_requested_metadata_in_stable_order(self) -> None:
        self._create_module("beta_module", features="beta features", future="beta future")
        self._create_module("alpha_module", features="alpha features", future="alpha future")

        result = ProjectFileReader(self.root).read_module_metadata(document_kind="both")

        self.assertEqual(
            [
                ("alpha_module", "FEATURES.md"),
                ("alpha_module", "FUTURE_UPDATES.md"),
                ("beta_module", "FEATURES.md"),
                ("beta_module", "FUTURE_UPDATES.md"),
            ],
            [(item.module_name, item.file_name) for item in result.documents],
        )
        self.assertEqual("alpha features", result.documents[0].content)

    def test_rejects_unknown_document_kind_and_unverified_module(self) -> None:
        self._create_module("safe_module", features="features", future="future")
        reader = ProjectFileReader(self.root)

        with self.assertRaises(ValueError):
            reader.read_module_metadata(document_kind="README.md")
        with self.assertRaises(ProjectModuleNotFoundError):
            reader.read_module_metadata("missing_module")

    def test_reports_document_removed_during_metadata_read(self) -> None:
        module = self._create_module("safe_module", features="features", future="future")
        reader = ProjectFileReader(self.root)
        original_read = reader.read_module_file

        def remove_future_before_read(module_name: str, file_name: str, max_characters: int):
            if file_name == "FUTURE_UPDATES.md":
                (module / file_name).unlink()
            return original_read(module_name, file_name, max_characters)

        reader.read_module_file = remove_future_before_read  # type: ignore[method-assign]

        result = reader.read_module_metadata("safe_module")

        self.assertEqual(["FEATURES.md"], [item.file_name for item in result.documents])
        self.assertEqual(("safe_module/FUTURE_UPDATES.md",), result.missing)

    def test_metadata_read_uses_one_aggregate_character_limit(self) -> None:
        self._create_module("safe_module", features="abcdefghij", future="future")

        result = ProjectFileReader(self.root).read_module_metadata("safe_module", max_characters=5)

        self.assertTrue(result.truncated)
        self.assertLessEqual(sum(len(item.content) for item in result.documents), 5)

    def test_metadata_bound_includes_memory_labels_and_short_document_overhead(self) -> None:
        for number in range(4):
            self._create_module(f"module_{number}", features="x", future="y")

        result = self.reader.read_module_metadata(
            document_kind="features",
            max_characters=100,
            format_payload=MetadataAnnotation._format_content,
        )

        payload = MetadataAnnotation._format_content(result.documents, result.missing, result.truncated)
        self.assertLessEqual(len(payload), 100)
        self.assertTrue(result.truncated)

    def test_metadata_bound_includes_missing_path_notices(self) -> None:
        self._create_module("sample_module", features="x", future="y")
        original_read = self.reader.read_module_file

        def missing_metadata(module_name: str, file_name: str, max_characters: int):
            if file_name == "FEATURES.md":
                raise ProjectFileNotFoundError(file_name, [])
            return original_read(module_name, file_name, max_characters)

        self.reader.read_module_file = missing_metadata  # type: ignore[method-assign]
        result = self.reader.read_module_metadata(
            "sample_module",
            max_characters=120,
            format_payload=MetadataAnnotation._format_content,
        )

        payload = MetadataAnnotation._format_content(result.documents, result.missing, result.truncated)
        self.assertLessEqual(len(payload), 120)
        self.assertEqual(("sample_module/FEATURES.md",), result.missing)
        self.assertTrue(result.truncated)


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
            received_contexts: list[str | None] = []

            def capture(message: str, callable_context: str | None = None) -> dict[str, str]:
                received_contexts.append(callable_context)
                return {"response": message}

            workspace = ProjectFileWorkspace(file_reader=ProjectFileReader(root), handle_user_message=capture)

            workspace.ask_about_project_file("selected.py", "visual only", False, "not a range")
            workspace.ask_about_project_file("selected.py", "explain this", True, "2")

            self.assertEqual([None], received_contexts[:1])
            self.assertIn("2: second", received_contexts[1] or "")


if __name__ == "__main__":
    unittest.main()
