"""Unit tests for deep research and web customizer.
Created and developed by Sajan Rai for Zaya.
"""

import unittest
from unittest.mock import patch

from actions.deep_research import (
    deduplicate_and_rank_sources,
    deep_research,
    run_deep_research_cycle,
    synthesize_research_report,
)
from actions.web_customizer import generate_custom_theme_css, web_customize


class TestDeepResearch(unittest.TestCase):
    def test_deduplicate_and_rank_sources(self):
        sources = [
            {"title": "RTX 5070 Specs", "url": "https://nvidia.com/rtx-5070", "snippet": "Blackwell architecture details."},
            {"title": "Duplicate Nvidia", "url": "https://nvidia.com/rtx-5070/", "snippet": "Duplicate link."},
            {"title": "Other GPU", "url": "https://other.com/gpu", "snippet": "General gpu info."}
        ]
        deduped = deduplicate_and_rank_sources(sources, ["rtx", "5070"])
        # Should deduplicate nvidia.com/rtx-5070
        self.assertEqual(len(deduped), 2)
        # Higher relevance first
        self.assertIn("RTX 5070", deduped[0]["title"])

    @patch("actions.deep_research.search_web_sources")
    @patch("actions.deep_research.save_to_knowledge_base")
    def test_deep_research_cycle(self, mock_save_kb, mock_search):
        mock_search.return_value = [
            {"title": "Quantum Computing 2026", "url": "https://example.com/qc", "snippet": "Breakthrough in topological qubits."}
        ]
        mock_save_kb.return_value = 1

        result = deep_research({"topic": "Quantum Computing", "depth": "quick"})
        self.assertIn("Quantum Computing", result)
        self.assertIn("quantum_computing.md", result)
        mock_save_kb.assert_called_once()


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
