import unittest
from core.diagnostics import inspect


class DiagnosticsTests(unittest.TestCase):
    def test_provider_diagnostics_do_not_return_credentials(self):
        result = inspect('providers')
        self.assertEqual(result.status, 'success')
        self.assertIn('gemini_key_present', result.data['providers'])
        self.assertNotIn('gemini_api_key', result.data['providers'])
