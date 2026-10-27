import unittest
import tempfile
from pathlib import Path
from actions.code_search import fast_code_search, search_code_in_directory

class TestCodeSearch(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

        # Create dummy code files
        (self.root / "auth.py").write_text("def authenticate_user(token):\n    # secret key\n    return token == 'valid'\n", encoding="utf-8")
        (self.root / "routes.py").write_text("from auth import authenticate_user\n\ndef login():\n    pass\n", encoding="utf-8")
        (self.root / "data.txt").write_text("ignore this file\n", encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_search_code_matches(self):
        matches = search_code_in_directory(
            root_dir=self.root,
            query="authenticate_user",
            extensions=[".py"]
        )
        self.assertEqual(len(matches), 2)
        # Verify file path and line number presence
        files_found = [m["file"] for m in matches]
        self.assertTrue(any("auth.py" in f for f in files_found))
        self.assertTrue(any("routes.py" in f for f in files_found))
        for m in matches:
            self.assertIn("line", m)
            self.assertIn("content", m)

    def test_search_regex(self):
        matches = search_code_in_directory(
            root_dir=self.root,
            query=r"def \w+\(",
            is_regex=True,
            extensions=[".py"]
        )
        self.assertGreaterEqual(len(matches), 2)

    def test_fast_code_search_action(self):
        res = fast_code_search({
            "query": "authenticate_user",
            "path": str(self.root)
        })
        self.assertIn("matches", res)
        self.assertIn("auth.py", res)

if __name__ == "__main__":
    unittest.main()
