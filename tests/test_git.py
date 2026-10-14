import subprocess
import tempfile
import unittest
from pathlib import Path
from core.git_utils import GitRepo


class GitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'work'
        self.path.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Zaya Test')
        self.repo = GitRepo(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.path, capture_output=True, text=True, check=True).stdout.strip()

    def commit_file(self, text='hello'):
        (self.path / 'hello.txt').write_text(text)
        self.assertEqual(self.repo.operate('stage', {'paths': ['hello.txt']}).status, 'success')
        self.assertIn('hello.txt', self.repo.operate('diff_staged', {}).data['stdout'])
        r = self.repo.operate('commit', {'message': 'test'})
        self.assertEqual(r.status, 'success', r)

    def test_real_commit_push_and_sha_verification(self):
        self.commit_file()
        bare = Path(self.tmp.name) / 'remote.git'
        self.git('init', '--bare', str(bare))
        self.git('remote', 'add', 'origin', str(bare))
        self.assertEqual(self.repo.operate('push', {}).status, 'success')
        self.assertEqual(self.repo.verify_push().data['remote_sha'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.repo.operate('create_branch', {'branch': 'feature'}).status, 'success')

    def test_secret_and_path_guards(self):
        (self.path / '.env').write_text('private')
        with self.assertRaises(ValueError):
            self.repo.safe_paths(['.env'])
        with self.assertRaises(ValueError):
            self.repo.safe_paths(['../outside'])
        with self.assertRaises(ValueError):
            self.repo.safe_paths([])
        with self.assertRaises(ValueError):
            self.repo.branch('--force')

    def test_rejected_push_is_failure(self):
        self.commit_file()
        bare = Path(self.tmp.name) / 'remote.git'
        self.git('init', '--bare', str(bare))
        self.git('remote', 'add', 'origin', str(bare))
        self.assertEqual(self.repo.operate('push', {}).status, 'success')
        self.git('checkout', '--orphan', 'other')
        self.git('commit', '-m', 'unrelated')
        r = self.repo.run('push', 'origin', 'other:main')
        self.assertEqual(r.status, 'failed')

    def test_not_repository(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        with self.assertRaises(ValueError):
            GitRepo(outside)
