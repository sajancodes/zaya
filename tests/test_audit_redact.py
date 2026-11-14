import unittest
from core.audit import redact

class AuditRedactTests(unittest.TestCase):
    def test_secret_fields_redacted(self):
        data = {
            'api_key': 'secret123',
            'token': 'tok456',
            'user_password': 'pass',
            'cookie': 'sess=xyz',
            'private_key': 'pemdata',
            'authorization': 'Bearer abc'
        }
        res = redact(data)
        for k in data:
            self.assertEqual(res[k], '[REDACTED]')

    def test_innocent_key_fields_preserved(self):
        data = {
            'hotkey': 'ctrl+alt+t',
            'keyboard': 'mechanical',
            'keyword': 'search_term',
            'public_key_type': 'rsa',
            'key_name': 'home_key'
        }
        res = redact(data)
        self.assertEqual(res['hotkey'], 'ctrl+alt+t')
        self.assertEqual(res['keyboard'], 'mechanical')
        self.assertEqual(res['keyword'], 'search_term')

if __name__ == '__main__':
    unittest.main()
