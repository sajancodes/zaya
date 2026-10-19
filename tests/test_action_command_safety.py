import unittest
from unittest.mock import patch

from actions import computer_control, open_app


class ActionCommandSafetyTests(unittest.TestCase):
    def test_windows_protocol_does_not_pass_through_command_shell(self):
        uri = 'ms-settings:display& echo injected'
        with patch.object(open_app.shutil, 'which', return_value=None), \
                patch.object(open_app.os, 'startfile', create=True) as start, \
                patch.object(open_app.subprocess, 'Popen') as popen, \
                patch.object(open_app.time, 'sleep'):
            self.assertTrue(open_app._launch_windows(uri))
        start.assert_called_once_with(uri)
        popen.assert_not_called()

    def test_resolved_executable_is_one_argument_without_shell(self):
        with patch.object(open_app.shutil, 'which', return_value=r'C:\Apps\Example.exe'), \
                patch.object(open_app.subprocess, 'Popen') as popen, \
                patch.object(open_app.time, 'sleep'):
            self.assertTrue(open_app._launch_windows('Example'))
        self.assertEqual(popen.call_args.args[0], [r'C:\Apps\Example.exe'])
        self.assertFalse(popen.call_args.kwargs['shell'])

    def test_powershell_window_title_is_single_quoted_data(self):
        title = "Joe's $(Remove-Item x); window"
        with patch.object(computer_control, '_get_os', return_value='windows'), \
                patch.object(computer_control.subprocess, 'run') as run, \
                patch.object(computer_control.time, 'sleep'):
            computer_control._focus_window(title)
        self.assertIn("AppActivate('Joe''s $(Remove-Item x); window')", run.call_args.args[0][-1])

    def test_applescript_receives_title_as_argument(self):
        title = '" & do shell script "evil'
        with patch.object(computer_control, '_get_os', return_value='mac'), \
                patch.object(computer_control.subprocess, 'run') as run, \
                patch.object(computer_control.time, 'sleep'):
            computer_control._focus_window(title)
        argv = run.call_args.args[0]
        self.assertEqual(argv[-1], title)
        self.assertNotIn(title, argv[-2])

    def test_screen_key_uses_shared_key_pool(self):
        with patch('core.gemini.api_key', return_value='plural-config-key'):
            self.assertEqual(computer_control._get_api_key(), 'plural-config-key')
