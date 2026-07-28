"""Focused non-GUI tests for the Canvas module facade."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from canvas_module import CanvasModule, CanvasWorkspaceDescriptor


class CanvasModuleTests(unittest.TestCase):
    def test_workspace_descriptor_is_stable_and_typed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            module = CanvasModule(Path(temporary_directory))
            descriptor = module.get_workspace_descriptor()

        self.assertIsInstance(descriptor, CanvasWorkspaceDescriptor)
        self.assertEqual("main", descriptor.workspace_id)
        self.assertEqual("AMADEUS Canvas", descriptor.title)
        self.assertEqual("foundation_ready", descriptor.status)
        self.assertEqual(1, descriptor.schema_version)

    def test_custom_workspace_id_is_preserved(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            descriptor = CanvasModule(Path(temporary_directory), workspace_id="brainstorm").get_workspace_descriptor()

        self.assertEqual("brainstorm", descriptor.workspace_id)


if __name__ == "__main__":
    unittest.main()
