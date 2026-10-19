import tempfile
import unittest
from pathlib import Path
from core.action_loader import discover_actions
from core.plugin_loader import discover_plugins


class PluginDiscoveryTests(unittest.TestCase):
    def test_repo_startup_discovery_has_no_game_updater_collision(self):
        repo_root = Path(__file__).resolve().parent.parent
        actions = discover_actions(repo_root / 'actions')
        self.assertIn('game_updater', actions.names())

        plugins = discover_plugins(repo_root / 'plugins', core_tool_names=actions.names())
        rejected = [r for r in plugins._all_records if not r.valid]
        game_updater_rejected = [r for r in rejected if r.name == 'game_updater']
        self.assertEqual(len(game_updater_rejected), 0,
                         f"game_updater should not be reported as collision, but got: {game_updater_rejected}")
        # All production plugins in repo should be valid
        self.assertEqual(len(rejected), 0, f"Expected 0 rejected plugins in repo, got: {rejected}")

    def test_synthetic_collision_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            collision_plugin = tmp / 'game_updater.py'
            collision_plugin.write_text(
                'PLUGIN = {"name": "game_updater", "description": "dup", "parameters": {"type": "OBJECT", "properties": {}}}\n'
                'def run(parameters):\n    return "dup"\n',
                encoding='utf-8'
            )
            plugins = discover_plugins(tmp, core_tool_names={'game_updater'})
            rejected = [r for r in plugins._all_records if not r.valid]
            self.assertEqual(len(rejected), 1)
            self.assertIn('collides with a core tool', rejected[0].error)
