"""Tests for Live session modularization (live_tools and audio_pipeline)."""
import json
import unittest

from core.live_tools import (
    INLINE_TOOL_DECLARATIONS,
    compact_tool_declarations,
    compact_tool_schema,
)


class TestLiveTools(unittest.TestCase):
    def test_inline_tool_declarations_valid(self):
        self.assertGreaterEqual(len(INLINE_TOOL_DECLARATIONS), 8)
        names = {t["name"] for t in INLINE_TOOL_DECLARATIONS}
        expected = {
            "system_status",
            "screen_process",
            "close_camera",
            "manage_monitor",
            "shutdown_jarvis",
            "save_memory",
            "recall_memory",
            "undo",
        }
        self.assertTrue(expected.issubset(names))

    def test_compact_tool_schema_preserves_structure(self):
        sample = {
            "name": "test_tool",
            "description": "First sentence is concise. Second sentence adds details. Third sentence is superfluous rambling that bloats the prompt token budget.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "param_one": {
                        "type": "STRING",
                        "description": "Primary param definition. Secondary context note. Tertiary redundant example that takes up lots of room.",
                    },
                    "param_two": {
                        "type": "INTEGER",
                    },
                },
                "required": ["param_one"],
            },
        }

        compacted = compact_tool_schema(sample)
        self.assertEqual(compacted["name"], "test_tool")
        self.assertEqual(compacted["parameters"]["type"], "OBJECT")
        self.assertEqual(compacted["parameters"]["required"], ["param_one"])
        self.assertIn("param_two", compacted["parameters"]["properties"])

        # Description length was reduced
        self.assertLess(len(compacted["description"]), len(sample["description"]))
        self.assertLess(len(compacted["parameters"]["properties"]["param_one"]["description"]),
                        len(sample["parameters"]["properties"]["param_one"]["description"]))

    def test_compaction_reduction_rate(self):
        declarations = [
            {
                "name": f"verbose_tool_{i}",
                "description": (
                    f"This is verbose description for tool {i}. It includes many unnecessary sentences. "
                    "Another long explanation here detailing every edge case and historical rationale. "
                    "And even more unnecessary text to simulate heavily documented legacy plugins."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "opt": {
                            "type": "STRING",
                            "description": (
                                "First sentence for parameter. Second sentence with details. "
                                "Third sentence with paragraphs of documentation that inflate context."
                            ),
                        }
                    },
                },
            }
            for i in range(10)
        ]

        compacted = compact_tool_declarations(declarations)
        orig_len = len(json.dumps(declarations))
        comp_len = len(json.dumps(compacted))
        reduction = (1.0 - comp_len / orig_len) * 100
        self.assertGreater(reduction, 30.0)


if __name__ == "__main__":
    unittest.main()
