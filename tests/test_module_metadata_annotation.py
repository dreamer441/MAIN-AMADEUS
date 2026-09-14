"""Focused tests for the explicit verified module metadata annotation."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from annotation_module import AnnotationParser, AnnotationResult, AnnotationSuggestionService
from annotation_module.annotations.metadata_annotation import MetadataAnnotation
from project_file_reader import ProjectFileReader


class ModuleMetadataAnnotationTests(unittest.TestCase):
    """Verify metadata commands only reach the fixed-file reader contract."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        module = root / "sample_module"
        module.mkdir()
        (module / "README.md").write_text("# Sample\n", encoding="utf-8")
        (module / "FEATURES.md").write_text("exact FEATURES text", encoding="utf-8")
        (module / "FUTURE_UPDATES.md").write_text("exact FUTURE_UPDATES text", encoding="utf-8")
        self.reader = ProjectFileReader(root)
        self.context = SimpleNamespace(file_reader=self.reader)
        self.handler = MetadataAnnotation()
        self.parser = AnnotationParser()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_module_both_returns_memory_panel_with_source_labels(self) -> None:
        result = self.handler.handle(
            self.parser.parse("[metadata][module][sample_module][both]"), self.context
        )

        self.assertIsInstance(result, AnnotationResult)
        self.assertEqual("memory", result.side_panel["type"])
        self.assertFalse(result.side_panel["metadata"]["include_chat_context"])
        self.assertIn("sample_module/FEATURES.md", result.side_panel["content"])
        self.assertIn("sample_module/FUTURE_UPDATES.md", result.side_panel["content"])

    def test_suggestions_preserve_each_complete_command_prefix(self) -> None:
        suggestions = AnnotationSuggestionService(self.reader, self.parser)

        self.assertEqual(
            {"[metadata][all]", "[metadata][module]"},
            {item["insert_text"] for item in suggestions.get_suggestions("[metadata]")},
        )
        self.assertEqual(
            {"[metadata][all][features]", "[metadata][all][future]", "[metadata][all][both]"},
            {item["insert_text"] for item in suggestions.get_suggestions("[metadata][all]")},
        )
        self.assertEqual(
            {"[metadata][module][sample_module]"},
            {item["insert_text"] for item in suggestions.get_suggestions("[metadata][module]")},
        )
        self.assertEqual(
            {
                "[metadata][module][sample_module][features]",
                "[metadata][module][sample_module][future]",
                "[metadata][module][sample_module][both]",
            },
            {
                item["insert_text"]
                for item in suggestions.get_suggestions("[metadata][module][sample_module]")
            },
        )

    def test_invalid_shapes_return_usage_without_reader_calls(self) -> None:
        calls: list[tuple[str, str]] = []
        context = SimpleNamespace(
            file_reader=SimpleNamespace(
                read_module_metadata=lambda module_name, document_kind: calls.append((module_name, document_kind))
            )
        )

        result = self.handler.handle(
            self.parser.parse("[metadata][module][sample_module][README.md]"), context
        )

        self.assertIsInstance(result, str)
        self.assertIn("[metadata][all][features|future|both]", result)
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
