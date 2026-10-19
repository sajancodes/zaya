"""Unit tests for KnowledgeStore SQLite FTS5 store and memory_manager hybrid search."""
import tempfile
import unittest
from pathlib import Path

from memory.knowledge_store import KnowledgeStore


class TestKnowledgeStore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_knowledge.db"
        self.store = KnowledgeStore(db_path=self.db_path)

    def tearDown(self):
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_put_get_delete_fact(self):
        self.store.put_fact("preferences", "favorite_editor", "VS Code")
        fact = self.store.get_fact("preferences", "favorite_editor")
        self.assertIsNotNone(fact)
        self.assertEqual(fact["value"], "VS Code")

        # Update fact
        self.store.put_fact("preferences", "favorite_editor", "Cursor")
        fact2 = self.store.get_fact("preferences", "favorite_editor")
        self.assertEqual(fact2["value"], "Cursor")

        # Delete fact
        ok = self.store.delete_fact("preferences", "favorite_editor")
        self.assertTrue(ok)
        self.assertIsNone(self.store.get_fact("preferences", "favorite_editor"))

    def test_entity_relations(self):
        self.store.record_relation("Sajan", "creator_of", "Zaya", weight=1.0)
        self.store.record_relation("Zaya", "runs_on", "Windows", weight=0.9)

        sajan_rels = self.store.get_relations("Sajan")
        self.assertEqual(len(sajan_rels), 1)
        self.assertEqual(sajan_rels[0]["relation"], "creator_of")
        self.assertEqual(sajan_rels[0]["target_entity"], "zaya")

        zaya_rels = self.store.get_relations("Zaya")
        self.assertEqual(len(zaya_rels), 2)

    def test_fts5_bm25_search(self):
        self.store.put_fact("projects", "zaya", "Autonomous personal Jarvis assistant")
        self.store.put_fact("projects", "opencode", "AI coding agent framework")
        self.store.put_fact("preferences", "beverage", "Cold brew coffee")

        results = self.store.search_hybrid("assistant", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "zaya")
        self.assertEqual(results[0]["category"], "projects")

        coffee_res = self.store.search_hybrid("coffee", limit=5)
        self.assertGreaterEqual(len(coffee_res), 1)
        self.assertEqual(coffee_res[0]["key"], "beverage")

    def test_sync_from_json(self):
        mock_mem = {
            "identity": {"name": {"value": "Sajan"}},
            "preferences": {"music": {"value": "Ambient electronic"}},
        }
        synced = self.store.sync_from_json(mock_mem)
        self.assertEqual(synced, 2)

        fact = self.store.get_fact("preferences", "music")
        self.assertIsNotNone(fact)
        self.assertEqual(fact["value"], "Ambient electronic")


if __name__ == "__main__":
    unittest.main()
