import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from actions.terminal_exec import terminal_exec
from core import confirm
from core.execution_policy import (classify, trust_context, TRUST_AUTHENTICATED_REMOTE_OWNER,
                                   TRUST_EXTERNAL_MESSAGE, TRUST_WEB_CONTENT, TRUST_TOOL_OUTPUT)
from core.operator import Operator
from core.task_runtime import TaskRuntime
from memory import config_manager as config


class AutomaticExecutionTests(unittest.TestCase):
    def test_saved_mode_is_explicit_and_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api_keys.json'
            path.write_text(json.dumps({'voice_name': 'Nika', 'gemini_api_key': 'test-key'}))
            with patch.object(config, 'CONFIG_DIR', Path(folder)), patch.object(config, 'CONFIG_FILE', path):
                self.assertFalse(config.get_auto_execute_enabled())
                config.save_auto_execute_enabled(True)
                self.assertTrue(config.get_auto_execute_enabled())
                self.assertEqual(config.load_api_keys()['gemini_api_key'], 'test-key')
                self.assertEqual(config.load_api_keys()['voice_name'], 'Nika')
                self.assertEqual(classify('python -c "print(1)"').level, 'normal')
                config.save_auto_execute_enabled(False)
                self.assertFalse(config.get_auto_execute_enabled())
                self.assertEqual(classify('python -c "print(1)"').level, 'confirm')
                with self.assertRaises(ValueError):
                    config.save_auto_execute_enabled('yes')
        for value in ['true', 'false', 1, None]:
            with patch.object(config, 'load_api_keys', return_value={'auto_execute_owner': value}):
                self.assertFalse(config.get_auto_execute_enabled())

    def test_full_mode_allows_owner_commands_but_preserves_read_and_empty_decisions(self):
        with patch.object(config, 'get_auto_execute_enabled', return_value=True):
            for command in ['git reset --hard', 'powershell -Command echo hi', 'echo a; echo b', 'Remove-Item temporary-file']:
                self.assertEqual(classify(command).level, 'normal')
            self.assertEqual(classify('git status').level, 'read')
            self.assertEqual(classify('   ').level, 'deny')
            token = trust_context.set(TRUST_AUTHENTICATED_REMOTE_OWNER)
            try:
                self.assertEqual(classify('echo a; echo b').level, 'normal')
                with self.assertRaises(PermissionError):
                    config.save_auto_execute_enabled(True)
            finally:
                trust_context.reset(token)

    def test_external_sources_cannot_execute_or_enable_full_mode(self):
        run = Mock()
        with patch.object(config, 'get_auto_execute_enabled', return_value=True):
            for source in [TRUST_EXTERNAL_MESSAGE, TRUST_WEB_CONTENT, TRUST_TOOL_OUTPUT]:
                token = trust_context.set(source)
                try:
                    with self.assertRaises(PermissionError):
                        classify('echo hello')
                    with self.assertRaises(PermissionError):
                        config.save_auto_execute_enabled(True)
                    with self.assertRaises(PermissionError):
                        confirm.request('test', 'Test', 'External content', run)
                    with self.assertRaises(PermissionError):
                        terminal_exec({'command': 'echo hello', 'confirmed': True})
                finally:
                    trust_context.reset(token)
        run.assert_not_called()

    def test_other_owner_actions_execute_once_without_a_confirmation_ui(self):
        run = Mock(return_value='Action completed with evidence.')
        with patch.object(config, 'get_auto_execute_enabled', return_value=True), \
                patch.object(confirm, '_show_cb', None):
            result = confirm.request('test', 'Owner action', 'Authorized local operation', run)
        self.assertEqual(result, 'Action completed with evidence.')
        run.assert_called_once()

    def test_real_compound_command_outside_project_records_output_exit_and_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'zaya-auto-test.txt'
            if sys.platform == 'win32':
                quoted = "'" + str(target).replace("'", "''") + "'"
                command = f"Set-Content -LiteralPath {quoted} -Value 'automatic execution verified'; Get-Content -LiteralPath {quoted}; Remove-Item -LiteralPath {quoted}"
            else:
                import shlex
                quoted = shlex.quote(str(target))
                command = f"printf 'automatic execution verified' > {quoted}; cat {quoted}; rm {quoted}"
            runtime = TaskRuntime()

            async def execute():
                return await Operator(runtime).execute('terminal_exec', lambda: asyncio.to_thread(
                    terminal_exec, {'command': command, 'cwd': folder, 'session_id': 'automatic-test'}))

            try:
                with patch.object(config, 'get_auto_execute_enabled', return_value=True), \
                        patch.object(confirm, 'request') as gate:
                    result = asyncio.run(execute())
                gate.assert_not_called()
                self.assertEqual(result.status, 'success', result.summary)
                self.assertEqual(result.data['exit_code'], 0)
                self.assertIn('automatic execution verified', result.data['stdout'])
                self.assertFalse(target.exists())
                self.assertTrue(result.evidence)
                self.assertTrue(result.side_effect)
                self.assertEqual(runtime.list()[0].state, 'completed')
            finally:
                runtime.db.close()

    def test_settings_toggle_is_persisted_and_can_be_turned_off(self):
        script = '''
import tempfile
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from ui import JarvisUI
from memory import config_manager as config
app=QApplication([])
with tempfile.TemporaryDirectory() as folder,patch.object(config,'CONFIG_DIR',Path(folder)),patch.object(config,'CONFIG_FILE',Path(folder)/'api_keys.json'):
    ui=JarvisUI('face.png');button=ui._win._auto_execute_btn
    assert not button.isChecked() and not config.get_auto_execute_enabled()
    button.click();assert button.isChecked() and config.get_auto_execute_enabled()
    assert button.text()=='FULL ACCESS: ON'
    ui._bar.shutdown();ui._win._unsubscribe_runtime();ui._win.close()
    ui=JarvisUI('face.png');button=ui._win._auto_execute_btn
    assert button.isChecked() and button.text()=='FULL ACCESS: ON'
    button.click();assert not button.isChecked() and not config.get_auto_execute_enabled()
    ui._bar.shutdown();ui._win._unsubscribe_runtime();ui._win.close()
print('Automatic owner command settings verified')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=25, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Automatic owner command settings verified', result.stdout)
