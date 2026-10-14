import unittest
from core.site_registry import normalize_git_remote, resolve_url, matches


class BrowserTests(unittest.TestCase):
    def test_repository_urls(self):
        for value in ['git@github.com:sajancodes/zaya.git', 'https://github.com/sajancodes/zaya.git', 'ssh://git@github.com/sajancodes/zaya.git']:
            self.assertEqual(normalize_git_remote(value), 'https://github.com/sajancodes/zaya')

    def test_known_sites_and_bad_urls(self):
        self.assertEqual(resolve_url('whatsapp web'), 'https://web.whatsapp.com/')
        for value in ['javascript://alert(1)', 'https://', 'https://user:password@github.com', 'random unknown site']:
            with self.assertRaises(ValueError):
                resolve_url(value)

    def test_exact_postcondition(self):
        self.assertTrue(matches('https://github.com/a/b', 'https://github.com/a/b/'))
        self.assertFalse(matches('https://github.com/a/b', 'https://github.com/login'))
        self.assertFalse(matches('https://github.com/a/b', 'https://evil.example/a/b'))
