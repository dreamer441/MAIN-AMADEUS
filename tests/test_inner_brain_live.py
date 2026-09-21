"""Opt-in synthetic checks against the configured local Nemotron, without user storage.

Set AMADEUS_RUN_LIVE_MODEL_TESTS=1 and run unittest discovery for this file.
These tests exercise model quality separately from deterministic regressions.
"""

import os
import unittest

from inner_brain import InnerBrainService
from llm_client import OllamaClient


@unittest.skipUnless(os.environ.get('AMADEUS_RUN_LIVE_MODEL_TESTS') == '1', 'Opt-in local model checks')
class InnerBrainLiveTests(unittest.TestCase):
    """Use public synthetic prompts and never read or modify application data."""

    def setUp(self):
        self.brain = InnerBrainService(OllamaClient(
            model='nemotron-3-nano:4b', timeout_seconds=30, think=False,
            response_format='json', temperature=0,
        ))

    def test_intents_and_non_actions(self):
        cases = (
            ('How are you?', 'chat', '', ''),
            ('Show my project files', 'flow', 'file', ''),
            ('List my sheets', 'chat', 'sheet', ''),
            ('What exports exist?', 'flow', 'export', ''),
            ('Create a planning sheet', 'chat', '', 'sheet'),
            ('Do not create a chat', 'chat', '', ''),
            ('What is planned for memory?', 'chat', 'metadata', ''),
            ('What workspace evidence is linked?', 'chat', 'mindmap', ''),
        )
        for message, route, read, creation in cases:
            with self.subTest(message=message):
                result = self.brain.analyze_message(message, route=route)
                self.assertTrue(result.succeeded, result.error)
                self.assertEqual(read, result.read_annotation)
                self.assertEqual(creation, result.creation_kind)
                if read == 'metadata':
                    self.assertEqual(('memory_module', 'future', 'answer'), (
                        result.metadata_module, result.metadata_document_kind, result.metadata_mode,
                    ))

    def test_summary_retains_latest_correction(self):
        result = self.brain.analyze_chat(
            'User: We will build a weather station. The budget is 80 dollars.\n'
            'User: Correction: the budget is 95 dollars. We chose a Raspberry Pi.'
        )
        self.assertTrue(result.succeeded, result.error)
        self.assertTrue(all((result.title, result.description, result.short_bullets, result.detailed_summary)))
        self.assertIn('95', result.detailed_summary)
        self.assertIn('Raspberry Pi', result.detailed_summary)
        self.assertEqual(('', ()), (result.creation_kind, result.suggested_write_actions))


if __name__ == '__main__':
    unittest.main()
