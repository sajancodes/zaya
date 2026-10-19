import unittest
from core.diagnostics import inspect


class DiagnosticsTests(unittest.TestCase):
    def test_provider_diagnostics_do_not_return_credentials(self):
        result = inspect('providers')
        self.assertEqual(result.status, 'success')
        self.assertIn('gemini_key_present', result.data['providers'])
        self.assertNotIn('gemini_api_key', result.data['providers'])

    def test_diagnose_bottleneck_structure(self):
        from core.diagnostics import diagnose_bottleneck
        result = diagnose_bottleneck(top_n=3)
        self.assertEqual(result.status, 'success')
        self.assertIn('top_cpu_processes', result.data)
        self.assertIn('top_memory_processes', result.data)
        self.assertIn('overall_cpu_percent', result.data)
        self.assertIn('overall_ram_percent', result.data)
        self.assertTrue(len(result.data['top_cpu_processes']) <= 3)

    def test_inspect_bottleneck_action(self):
        result = inspect('bottleneck')
        self.assertEqual(result.status, 'success')
        self.assertIn('bottleneck', result.data)
        self.assertIn('top_cpu_processes', result.data['bottleneck'])
