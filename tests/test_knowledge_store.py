"""Unit tests for KnowledgeStore SQLite FTS5 store, aliases, expiration, boosting, and memory_manager hybrid search."""
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from memory.knowledge_store import KnowledgeStore, get_knowledge_store
from memory.memory_manager import _truncate_value, update_memory, load_memory
import memory.memory_manager as mm


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

    def test_category_value_truncation(self):
        # Identity/Preferences/Relationships limit: 380
        long_pref = "A" * 500
        truncated_pref = _truncate_value(long_pref, "preferences")
        self.assertEqual(len(truncated_pref), 381)  # 380 chars + '…'
        self.assertTrue(truncated_pref.endswith("…"))

        # Projects/Notes limit: 1200
        long_project = "B" * 1500
        truncated_project = _truncate_value(long_project, "projects")
        self.assertEqual(len(truncated_project), 1201)  # 1200 chars + '…'
        self.assertTrue(truncated_project.endswith("…"))

        # Under limit preserves full value
        short_val = "Compact fact"
        self.assertEqual(_truncate_value(short_val, "identity"), short_val)

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

    def test_entity_relations_and_boosting(self):
        self.store.record_relation("Sajan", "creator_of", "Zaya", weight=1.0)
        self.store.record_relation("Zaya", "runs_on", "Windows", weight=0.9)

        sajan_rels = self.store.get_relations("Sajan")
        self.assertEqual(len(sajan_rels), 1)
        self.assertEqual(sajan_rels[0]["relation"], "creator_of")
        self.assertEqual(sajan_rels[0]["target_entity"], "zaya")

        zaya_rels = self.store.get_relations("Zaya")
        self.assertEqual(len(zaya_rels), 2)

    def test_alias_lookup_and_expansion(self):
        self.store.record_alias("py", "python", "programming")
        resolved = self.store.resolve_alias("py", "programming")
        self.assertEqual(resolved, "python")

        resolved_generic = self.store.resolve_alias("py")
        self.assertEqual(resolved_generic, "python")

    def test_expiration_filtering(self):
        # 1. Unexpired fact (expires in year 2099)
        self.store.put_fact("wishes", "trip_future", "Trip to Mars", expires_at="2099-01-01T00:00:00Z")
        # 2. Expired fact (expired in year 2020)
        self.store.put_fact("wishes", "trip_past", "Trip to Moon", expires_at="2020-01-01T00:00:00Z")

        results = self.store.search_hybrid("trip", limit=5)
        keys = [r["key"] for r in results]
        self.assertIn("trip_future", keys)
        self.assertNotIn("trip_past", keys)

    def test_last_used_at_updated_only_on_returned_facts(self):
        self.store.put_fact("notes", "note_alpha", "Important note about alpha")
        self.store.put_fact("notes", "note_beta", "Important note about beta")

        # Search specifically for alpha
        results = self.store.search_hybrid("alpha", limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "note_alpha")

        fact_alpha = self.store.get_fact("notes", "note_alpha")
        fact_beta = self.store.get_fact("notes", "note_beta")

        self.assertIsNotNone(fact_alpha["last_used_at"])
        self.assertIsNone(fact_beta["last_used_at"])

    def test_db_path_derivation_from_memory_path(self):
        custom_mem_path = Path(self.tmp_dir.name) / "isolated" / "long_term.json"
        with unittest.mock.patch.object(mm, "MEMORY_PATH", custom_mem_path):
            from memory.knowledge_store import _derive_default_db_path
            derived = _derive_default_db_path()
            self.assertEqual(derived, custom_mem_path.parent / "knowledge.db")

    def test_corruption_recovery(self):
        self.store.put_fact("identity", "owner_name", "Sajan")
        # Intentionally corrupt the database file with garbage bytes
        self.db_path.write_bytes(b"THIS IS CORRUPT SQLITE DATABASE GARBAGE DATA 1234567890")

        # Calling store operation should detect database error and trigger recovery
        recovered_store = KnowledgeStore(db_path=self.db_path)
        recovered_store.put_fact("identity", "owner_name", "Sajan")
        fact = recovered_store.get_fact("identity", "owner_name")
        self.assertIsNotNone(fact)
        self.assertEqual(fact["value"], "Sajan")

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
