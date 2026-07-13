"""Focused tests for Phase 3 annotation block extraction."""

import unittest

from annotation_module.annotation_parser import AnnotationParser


class AnnotationParserTests(unittest.TestCase):
    """Verify blocks remain independent while legacy parsing remains available."""

    def setUp(self) -> None:
        self.parser = AnnotationParser()

    def test_extracts_annotation_embedded_in_normal_prompt(self) -> None:
        parsed = self.parser.parse_message("Summarize [identity][prompt][end] for me")

        self.assertEqual("Summarize  for me", parsed.normal_prompt)
        self.assertEqual("identity", parsed.blocks[0].annotation.annotation_name)
        self.assertEqual(["prompt"], parsed.blocks[0].annotation.arguments)
        self.assertTrue(parsed.blocks[0].is_terminated)

    def test_extracts_multiple_independent_blocks_in_source_order(self) -> None:
        parsed = self.parser.parse_message("[identity][end] explain [memory][list][end] now")

        self.assertEqual(["identity", "memory"], [block.annotation.annotation_name for block in parsed.blocks])
        self.assertEqual("explain  now", parsed.normal_prompt)

    def test_unterminated_block_consumes_the_rest_of_the_message(self) -> None:
        parsed = self.parser.parse_message("before [memory][global] keep [file] as content")

        self.assertEqual("before", parsed.normal_prompt)
        self.assertEqual("memory", parsed.blocks[0].annotation.annotation_name)
        self.assertEqual("keep [file] as content", parsed.blocks[0].annotation.content)
        self.assertFalse(parsed.blocks[0].is_terminated)

    def test_nested_annotation_text_does_not_create_a_nested_block(self) -> None:
        parsed = self.parser.parse_message("[memory][global] note [file][core][end] after")

        self.assertEqual(1, len(parsed.blocks))
        self.assertEqual("note [file][core]", parsed.blocks[0].annotation.content)
        self.assertEqual("after", parsed.normal_prompt)

    def test_legacy_leading_parse_is_preserved(self) -> None:
        legacy = self.parser.parse(" [file] [core.py] explain this")
        parsed_message = self.parser.parse_message(" [file] [core.py] explain this")

        self.assertIsNotNone(legacy)
        self.assertEqual("file", legacy.annotation_name)  # type: ignore[union-attr]
        self.assertTrue(parsed_message.is_legacy_leading_annotation)
        self.assertEqual("explain this", parsed_message.blocks[0].annotation.content)

    def test_unknown_annotation_is_extracted_for_registry_handling(self) -> None:
        parsed = self.parser.parse_message("Before [not-real] inspect this [end] after")

        self.assertEqual("not_real", parsed.blocks[0].annotation.annotation_name)
        self.assertEqual("inspect this", parsed.blocks[0].annotation.content)
        self.assertEqual("Before  after", parsed.normal_prompt)

    def test_empty_brackets_remain_normal_text(self) -> None:
        parsed = self.parser.parse_message("Before [] after")

        self.assertEqual([], parsed.blocks)
        self.assertEqual("Before [] after", parsed.normal_prompt)

    def test_text_after_end_is_outside_the_annotation_block(self) -> None:
        parsed = self.parser.parse_message("[identity] charter [end] Answer from the findings.")

        self.assertEqual("charter", parsed.blocks[0].annotation.content)
        self.assertEqual("Answer from the findings.", parsed.normal_prompt)


if __name__ == "__main__":
    unittest.main()
