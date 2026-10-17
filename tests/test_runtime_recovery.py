import unittest
from unittest.mock import patch


class LiveResumeRecoveryTests(unittest.TestCase):
    def test_expired_bidi_session_changes_resume_scope_without_marking_model_gone(self):
        from core.gemini_keys import error_text
        from memory.conversation_store import resume_scope

        before = resume_scope('models/gemini-3.8-live', 'Nika', 'fixture-key')
        nested = ExceptionGroup(
            'receive',
            [RuntimeError('1008 None. BidiGenerateContent session not found or expired')],
        )
        text = error_text(nested)
        after = resume_scope('models/gemini-3.8-live', 'Nika', 'fixture-key')

        self.assertNotEqual(before, after)
        self.assertIn('checkpoint expired', text.lower())
        self.assertNotIn('not found', text.lower())


class ProcessTerminationTests(unittest.TestCase):
    def test_common_names_resolve_to_task_manager_executables(self):
        from actions.process_terminate import _target_name

        self.assertEqual(_target_name('Task Manager'), 'taskmgr.exe')
        self.assertEqual(_target_name('Notepad'), 'notepad.exe')
        self.assertEqual(_target_name('Brave'), 'brave.exe')
        self.assertEqual(_target_name('Antigravity'), 'Antigravity.exe')

    def test_current_zaya_process_is_never_selected(self):
        import os
        from actions import process_terminate

        fake = type('P', (), {'info': {
            'pid': os.getpid(), 'ppid': 1, 'name': 'python.exe', 'exe': 'python.exe'
        }})()
        with patch.object(process_terminate.psutil, 'process_iter', return_value=[fake]):
            _target, matches = process_terminate._find_matches('python')
        self.assertEqual(matches, [])


class UiMediaErrorGuardTests(unittest.TestCase):
    def test_mainwindow_has_safe_log_forwarder_after_action_discovery_helper_import(self):
        import actions.ui_runtime_guard  # noqa: F401
        from ui import MainWindow
        self.assertTrue(hasattr(MainWindow, 'write_log'))


if __name__ == '__main__':
    unittest.main()
