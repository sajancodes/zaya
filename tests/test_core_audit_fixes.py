import tempfile
import unittest
from pathlib import Path
from core.task_runtime import TaskRuntime


class CachedResultTests(unittest.TestCase):
    def test_corrupt_cached_result_cannot_repeat_side_effect(self):
        runtime = TaskRuntime()
        try:
            for payload in ('{', '[]', '{"status":"success","summary":4}', '{"status":"bogus","summary":"x"}'):
                runtime.db.execute('INSERT OR REPLACE INTO tool_results VALUES (?,?)', ('call', payload))
                result = runtime.cached('call')
                self.assertEqual(result.status, 'failed')
                self.assertFalse(result.retryable)
                self.assertTrue(result.data['cached_result_invalid'])
        finally:
            runtime.db.close()


class FileScanTests(unittest.TestCase):
    def test_largest_files_scan_is_bounded_and_labels_partial_results(self):
        from unittest.mock import patch
        from actions import file_controller
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'one.txt').write_text('hello')
            with patch.object(file_controller, '_is_safe_path', return_value=True), patch.object(
                    file_controller.time, 'monotonic', side_effect=[0, 0, 6]):
                result = file_controller.get_largest_files(folder)
            self.assertIn('one.txt', result)
            self.assertIn('Partial scan', result)
