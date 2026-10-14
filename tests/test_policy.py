import unittest
from core.execution_policy import classify, trust_context, TRUST_EXTERNAL_MESSAGE


class PolicyTests(unittest.TestCase):
    def test_ordinary_operations(self):
        for command in ['git status', 'git diff --cached', 'git commit -m "test"', 'git push origin main', 'python -m unittest', 'Write-Output "git reset --hard"']:
            self.assertIn(classify(command).level, {'read', 'normal'}, command)

    def test_destructive_and_bypass_operations(self):
        for command in ['git reset --hard', 'git push --force-with-lease', 'git push origin +main', 'git clean -fd', 'Remove-Item x -Recurse', 'rm -rf x', 'git status; rm x', 'powershell -enc abcd', 'git -c alias.x=!rm x', 'python -c "print(1)"']:
            self.assertEqual(classify(command).level, 'confirm', command)

    def test_external_has_no_shell(self):
        token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
        try:
            with self.assertRaises(PermissionError):
                classify('git status')
        finally:
            trust_context.reset(token)
