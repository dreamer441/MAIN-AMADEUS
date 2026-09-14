"""Shared grammar tests for approval-gated creation annotations."""

import unittest

from annotation_module import AnnotationParser, AnnotationSuggestionService, parse_creation_annotation


class CreationAnnotationCommandTests(unittest.TestCase):
    def test_sheet_and_memory_create_forms_are_typed(self) -> None:
        sheet = parse_creation_annotation("[sheet][create] Sprint plan; scope: chat")
        memory = parse_creation_annotation("[memory][save] Keep decisions")
        assert sheet is not None and memory is not None
        self.assertEqual(("sheet", "Sprint plan", "chat"), (sheet.kind, sheet.request, sheet.explicit_scope))
        self.assertEqual(("memory", "Keep decisions", None), (memory.kind, memory.request, memory.explicit_scope))

    def test_legacy_workspace_commands_are_not_creation_annotations(self) -> None:
        self.assertIsNone(parse_creation_annotation("/create-sheet Sprint plan"))
        self.assertIsNone(parse_creation_annotation("/create-memory Keep decisions"))

    def test_blank_and_invalid_scope_requests_do_not_parse(self) -> None:
        self.assertIsNone(parse_creation_annotation("[sheet][create]"))
        request = parse_creation_annotation("[memory][save] Keep this; scope: nowhere")
        assert request is not None
        self.assertEqual("Keep this; scope: nowhere", request.request)

    def test_shared_suggestions_expose_creation_forms(self) -> None:
        class FileReader:
            pass

        suggestions = AnnotationSuggestionService(FileReader(), AnnotationParser())
        root = {item["insert_text"] for item in suggestions.get_suggestions("/")}
        sheet = {item["insert_text"] for item in suggestions.get_suggestions("[sheet]")}
        memory = {item["insert_text"] for item in suggestions.get_suggestions("[memory]")}
        self.assertTrue({"[sheet]", "[memory]", "/create-chat "}.issubset(root))
        self.assertIn("[sheet][create] ", sheet)
        self.assertIn("[memory][save] ", memory)


if __name__ == "__main__":
    unittest.main()
