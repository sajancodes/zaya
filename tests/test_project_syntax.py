import ast
from pathlib import Path
import unittest


class ProjectSyntaxTests(unittest.TestCase):
    def test_all_project_python_sources_parse(self):
        root = Path(__file__).resolve().parent.parent
        paths = list(root.glob('*.py'))
        for folder in ('core', 'actions', 'memory', 'config', 'dashboard', 'services', 'plugins', 'tests', 'tools'):
            paths.extend((root / folder).rglob('*.py'))
        for path in paths:
            if '__pycache__' in path.parts:
                continue
            with self.subTest(path=str(path.relative_to(root))):
                ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
