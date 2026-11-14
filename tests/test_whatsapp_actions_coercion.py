import unittest
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER
from actions.whatsapp import whatsapp

class ActionsWhatsAppCoercionTests(unittest.TestCase):
    def setUp(self):
        set_trust(TRUST_LOCAL_OWNER)

    def test_safe_limit_coercion(self):
        # Invalid string limit
        res_str = whatsapp({'action': 'recent', 'limit': 'invalid_abc'})
        self.assertIn(res_str.status, {'success', 'partial'})

        # None limit
        res_none = whatsapp({'action': 'recent', 'limit': None})
        self.assertIn(res_none.status, {'success', 'partial'})

        # Valid numeric limit
        res_valid = whatsapp({'action': 'recent', 'limit': 2})
        self.assertIn(res_valid.status, {'success', 'partial'})

if __name__ == '__main__':
    unittest.main()
