import unittest
import tempfile
from pathlib import Path
from actions.doc_generator import generate_document, create_powerpoint, create_excel_sheet
from actions.widget_forge import widget_forge, forge_live_widget

class TestDocGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_create_powerpoint(self):
        slides_data = [
            {"title": "Intro", "content": "Welcome to Zaya IRIS-MX."},
            {"title": "Features", "content": "Voice activation, Automation, Deep Research."}
        ]
        out_file = self.out_dir / "presentation.pptx"
        path = create_powerpoint("Zaya Overview", slides_data, out_path=out_file)
        self.assertTrue(Path(path).exists())
        self.assertGreater(Path(path).stat().st_size, 1000)

    def test_create_excel_sheet(self):
        headers = ["Task", "Status", "Priority"]
        rows = [
            ["Double-Clap", "Complete", "High"],
            ["Universal LLM", "Complete", "High"]
        ]
        out_file = self.out_dir / "tasks.xlsx"
        path = create_excel_sheet("Sprint Progress", headers, rows, out_path=out_file)
        self.assertTrue(Path(path).exists())
        self.assertGreater(Path(path).stat().st_size, 1000)

    def test_generate_document_action(self):
        res = generate_document({
            "doc_type": "presentation",
            "title": "Quarterly Report",
            "slides": [{"title": "Q1", "content": "Revenue grew 40%"}]
        })
        self.assertIn("success", res)
        self.assertIn(".pptx", res)

class TestWidgetForge(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_forge_live_widget(self):
        html_path = forge_live_widget("timer", out_dir=self.out_dir)
        self.assertTrue(Path(html_path).exists())
        content = Path(html_path).read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("Timer", content)

    def test_widget_forge_action(self):
        res = widget_forge({"widget_type": "calculator"})
        self.assertIn("success", res)
        self.assertIn("calculator", res.lower())

if __name__ == "__main__":
    unittest.main()
