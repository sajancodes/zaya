import unittest
from unittest.mock import MagicMock, patch
from memory.knowledge_store import get_knowledge_store
from core.passive_screen_watcher import passive_screen_watcher, ScreenContext


class TestKnowledgeAndPassiveIntelligence(unittest.TestCase):
    def test_knowledge_store_sync_and_hybrid_search(self):
        store = get_knowledge_store()
        store.put_fact("preferences", "favorite_ide", "VS Code")
        store.record_relation("Sajan", "uses", "VS Code")

        facts = store.search_hybrid("what ide do I use", limit=5)
        self.assertTrue(len(facts) > 0)
        keys = [f["key"] for f in facts]
        self.assertIn("favorite_ide", keys)

    def test_passive_screen_watcher_context(self):
        passive_screen_watcher._current_context = ScreenContext(
            app_name="terminal.exe",
            window_title="Administrator: Windows PowerShell",
            detected_error="pytest: command not found",
            error_type="terminal_error",
            has_error=True,
        )
        prompt = passive_screen_watcher.get_screen_context_prompt()
        self.assertIn("ACTIVE SCREEN CONTEXT", prompt)
        self.assertIn("pytest: command not found", prompt)


if __name__ == "__main__":
    unittest.main()
