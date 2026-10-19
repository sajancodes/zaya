import unittest
from unittest.mock import patch, MagicMock
from actions.deep_research import deep_research, run_deep_research_cycle
from actions.web_customizer import web_customize, generate_custom_theme_css

class TestDeepResearch(unittest.TestCase):
    @patch("actions.deep_research.search_web_sources")
    @patch("actions.deep_research.synthesize_research_report")
    def test_deep_research_cycle(self, mock_synth, mock_search):
        mock_search.return_value = [
            {"title": "Quantum Computing 2026", "url": "https://example.com/qc", "snippet": "Breakthrough in topological qubits."}
        ]
        mock_synth.return_value = "# Research Report: Quantum Computing\n\nRecent breakthroughs include topological qubits."

        result = deep_research({"topic": "Quantum Computing", "depth": "quick"})
        self.assertIn("Quantum Computing", result)
        self.assertIn("quantum_computing.md", result)

class TestWebCustomizer(unittest.TestCase):
    def test_generate_custom_theme_css(self):
        css = generate_custom_theme_css("cyberpunk")
        self.assertIn("#00ff66", css.lower())
        self.assertIn("!important", css)

    @patch("actions.web_customizer.inject_css_into_browser")
    def test_web_customize_action(self, mock_inject):
        mock_inject.return_value = {"status": "success", "message": "Injected theme cyberpunk"}
        res = web_customize({"theme": "cyberpunk"})
        self.assertIn("cyberpunk", res)
        self.assertIn("success", res)

if __name__ == "__main__":
    unittest.main()
