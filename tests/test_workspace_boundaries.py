"""Regression tests for workspace ownership, plain Sheet targets, and GUI routes."""
import ast
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from canvas_module import CanvasModule, CanvasTextBlock, CanvasConnector
from sheets_module.sheet_service import SheetService
from workspace_integration import MindMapWorkspaceSync
from mindmap.integrations.workspace_sync import MindMapWorkspaceSync as LegacySync


class WorkspaceBoundaryTests(unittest.TestCase):
    """Check owner interfaces without opening application storage or real windows."""

    def test_legacy_sync_import_is_same_owner(self):
        self.assertIs(LegacySync, MindMapWorkspaceSync)
        self.assertEqual('workspace_integration.workspace_sync', MindMapWorkspaceSync.__module__)

    def test_projection_rejects_invalid_records_without_overwriting_document(self):
        with TemporaryDirectory() as directory:
            canvas = CanvasModule(Path(directory))
            workspace = 'mindmap_projection'
            block = CanvasTextBlock(object_id='projection', workspace_id=workspace, text='Node', position_x=0, position_y=0,
                                    locked=True, metadata={'mindmap_projection': True})
            canvas.replace_mindmap_projection(workspace, blocks=(block,), connectors=())
            before = canvas.get_snapshot_for_workspace(workspace)
            invalid_connector = CanvasConnector(connector_id='broken', workspace_id=workspace,
                source_object_id=block.object_id, target_object_id='missing', metadata={'mindmap_projection': True})
            for blocks, connectors in [
                ((replace(block, metadata={}),), ()),
                ((replace(block, workspace_id='main'),), ()),
                ((block, block), ()),
                ((block,), (invalid_connector,)),
            ]:
                with self.subTest(blocks=blocks, connectors=connectors), self.assertRaises(ValueError):
                    canvas.replace_mindmap_projection(workspace, blocks=blocks, connectors=connectors)
                self.assertEqual(before, canvas.get_snapshot_for_workspace(workspace))
            with self.assertRaises(ValueError):
                canvas.replace_mindmap_projection('main', blocks=(), connectors=())

    def test_plain_sheet_resolution_preserves_scope_visibility_and_legacy_callers(self):
        with TemporaryDirectory() as directory:
            service = SheetService(Path(directory))
            chat = service.create_sheet('Plan', content='chat', chat_id='one')
            global_sheet = service.create_sheet('Plan', content='global', scope='global')
            self.assertEqual(chat, service.resolve_target('one', scope='chat', reference='Plan')[0])
            self.assertEqual(global_sheet, service.resolve_target('one', scope='global', reference='Plan')[0])
            self.assertIsNone(service.resolve_target('two', scope='chat', reference='Plan')[0])
            legacy = SimpleNamespace(arguments=['chat', 'Plan'], normalized_arguments=['chat', 'plan'])
            self.assertEqual(service.resolve_target('one', scope='chat', reference='Plan'),
                             service.resolve_annotation_target(legacy, 'one'))
            self.assertEqual((None, None, 'all'), service.resolve_target('one'))

    def test_annotation_interpretation_matches_legacy_results(self):
        from annotation_module.annotation_parser import AnnotationParser
        from annotation_module.annotations.sheet_annotation import resolve_sheet_annotation_target
        with TemporaryDirectory() as directory:
            service = SheetService(Path(directory))
            service.create_sheet('Mixed Case Plan', chat_id='one', content='chat')
            service.create_sheet('Global Plan', scope='global', content='global')
            for command in ('[sheet]', '[sheet][list]', '[sheet][list][CHAT]',
                            '[sheet][list][Unknown Scope]', '[sheet][chat]', '[sheet][global]',
                            '[sheet][chat][Mixed Case Plan]', '[sheet][global][Global Plan]',
                            '[sheet][Mixed Case Plan]', '[sheet][Missing]'):
                with self.subTest(command=command):
                    annotation = AnnotationParser().parse(command)
                    self.assertEqual(service.resolve_annotation_target(annotation, 'one'),
                                     resolve_sheet_annotation_target(service, annotation, 'one'))

    def test_sheets_does_not_import_annotation(self):
        tree = ast.parse(Path('sheets_module/sheet_service.py').read_text(encoding='utf-8'))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(any(name and name.startswith('annotation_module') for name in imports))

    def test_canvas_gui_loader_uses_only_core_route(self):
        tree = ast.parse(Path('canvas_module/gui/view.py').read_text(encoding='utf-8'))
        loader = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_load_module')
        loader.decorator_list = []
        namespace = {'Any': object}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[loader], type_ignores=[])), '<loader>', 'exec'), namespace)
        facade, raw_module = object(), object()
        self.assertIs(facade, namespace['_load_module'](SimpleNamespace(canvas=facade, canvas_module=raw_module)))
        self.assertIsNone(namespace['_load_module'](SimpleNamespace(canvas_module=raw_module)))

    def test_main_window_supplies_shared_habit_route(self):
        tree = ast.parse(Path('amadeus_gui/main/main_window.py').read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'HabitTrackerView']
        self.assertEqual(1, len(calls))
        value = next(keyword.value for keyword in calls[0].keywords if keyword.arg == 'service')
        self.assertEqual('self.core.habits', ast.unparse(value))


if __name__ == '__main__':
    unittest.main()
