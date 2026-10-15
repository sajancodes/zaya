"""Ordinary links never become an automated, signed-out browser session."""
import unittest
from unittest.mock import Mock, patch

from actions.browser_control import _open_native, browser_control
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, trust_context
from core.tool_result import ToolResult


class NativeBrowserTests(unittest.TestCase):
    def test_verify_and_existing_automation_do_not_change_native_profile(self):
        registry = Mock()
        registry.has.return_value = True
        with patch('actions.browser_control._registry', registry), \
                patch('memory.config_manager.load_api_keys', return_value={'preferred_browser': 'brave'}), \
                patch('actions.browser_control._open_native', return_value='Opened in brave: https://github.com/sajancodes/zaya') as launch:
            result = browser_control({'action': 'go_to', 'url': 'https://github.com/sajancodes/zaya', 'verify': True})
        launch.assert_called_once_with('https://github.com/sajancodes/zaya', 'brave')
        registry.get.assert_not_called()
        self.assertEqual(result.status, 'partial')
        self.assertFalse(result.data['verified'])
        self.assertEqual(result.data['mode'], 'native')

    def test_explicit_browser_overrides_preference_and_search_uses_native(self):
        with patch('memory.config_manager.load_api_keys', return_value={'preferred_browser': 'brave'}), \
                patch('actions.browser_control._registry'), \
                patch('actions.browser_control._open_native', return_value='Opened in firefox') as launch:
            browser_control({'action': 'search', 'query': 'Zaya assistant', 'browser': 'firefox'})
        launch.assert_called_once_with('https://www.google.com/search?q=Zaya+assistant', 'firefox')

    def test_native_brave_launch_has_no_automation_or_alternate_profile_flags(self):
        exe = r'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe'
        with patch('actions.browser_control._OS', 'Windows'), \
                patch('actions.browser_control._resolve_browser', return_value={'exe': exe}), \
                patch('actions.browser_control.subprocess.Popen') as launch:
            result = _open_native('https://github.com/sajancodes/zaya', 'brave')
        self.assertEqual(launch.call_args.args[0], [exe, 'https://github.com/sajancodes/zaya'])
        self.assertIn('Opened in brave', result)

    def test_explicit_automation_still_navigates_and_verifies(self):
        registry = Mock()
        session = registry.get.return_value
        session.go_to.return_value = 'coroutine fixture'
        session.run.return_value = ToolResult('success', 'verified', {'verified': True})
        with patch('actions.browser_control._registry', registry), \
                patch('memory.config_manager.load_api_keys', return_value={}), \
                patch('actions.browser_control._open_native') as launch:
            result = browser_control({'action': 'go_to', 'url': 'https://example.com', 'mode': 'automation'})
        self.assertEqual(result.status, 'success')
        launch.assert_not_called()
        session.go_to.assert_called_once_with('https://example.com')

    def test_launch_failure_does_not_claim_url_was_opened(self):
        with patch('actions.browser_control._open_native', return_value='Could not find a browser to open.'):
            result = browser_control({'action': 'go_to', 'url': 'https://example.com'})
        self.assertEqual(result.status, 'failed')
        self.assertFalse(result.data['launch_requested'])

    def test_git_open_remote_passes_exact_url_to_regular_browser(self):
        from core.git_utils import GitRepo
        repo = GitRepo.__new__(GitRepo)
        repo.text = Mock(return_value='git@github.com:sajancodes/zaya.git')
        with patch('actions.browser_control.browser_control', return_value=ToolResult('partial', 'launched')) as browser:
            repo.operate('open_remote', {})
        self.assertEqual(browser.call_args.args[0],
                         {'action': 'go_to', 'url': 'https://github.com/sajancodes/zaya', 'mode': 'native'})

    def test_non_owner_cannot_open_browser(self):
        token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
        try:
            with self.assertRaises(PermissionError):
                browser_control({'action': 'go_to', 'url': 'https://example.com'})
        finally:
            trust_context.reset(token)
