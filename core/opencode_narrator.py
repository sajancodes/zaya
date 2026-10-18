"""Short first-person progress beats derived from OpenCode events.

Speech uses local templates; model text and terminal output are never spoken
as instructions. Full bounded responses remain available through job status.
"""
import re
import time

from core.opencode_events import Tally

ISSUE = re.compile(r'\b(found|identified|discovered|root cause)\b.{0,100}\b(bug|issue|error|problem|cause|wrong|missing)\b|\b(the bug|the issue|the problem) is\b', re.I | re.S)
TEST = re.compile(r'\b(pytest|unittest|vitest|jest|go test|cargo test|npm test|npm run test|ruff)\b', re.I)


class Narrator:
    def __init__(self, project_name, *, now=time.monotonic):
        self.project = project_name
        self._now = now
        self._said = set()
        self._last_activity = now()
        self._last_heartbeat = now()
        self.progress = 'reading the project'
        self.tests = None

    def _once(self, key, text, progress):
        self.progress = progress
        if key in self._said:
            return []
        self._said.add(key)
        return [text]

    def feed(self, event):
        self._last_activity = self._now()
        if event.kind == 'text' and ISSUE.search(event.text):
            return self._once('issue', "I've found an issue here. I'm checking the cause.", 'found an issue')
        if not event.is_tool:
            return []
        if event.failed:
            return self._once('tool_error', "That step reported an error. I'm checking the result.", 'a step reported an error')
        if event.tool == 'read' and event.status == 'completed':
            return self._once('read', "I've got the file. I'm checking it now.", 'reading the files')
        if event.tool in {'grep', 'glob'}:
            return self._once('search', "I'm going through the project files.", 'searching the project')
        if event.tool in {'edit', 'write', 'patch', 'apply_patch'}:
            return self._once('edit', "I'm making the changes now.", 'editing the project')
        if event.tool in {'shell', 'bash'} and TEST.search(event.command):
            if event.status == 'completed' and event.exit_code is not None:
                self.tests = event.exit_code == 0
                return self._once('test_pass' if self.tests else 'test_fail',
                                  'The checks passed.' if self.tests else 'The checks found a problem.',
                                  'checks passed' if self.tests else 'checks failed')
            return self._once('test', "I'm running the checks now.", 'running checks')
        if event.tool == 'execute':
            return self._once('execute', "I'm working through the next step.", 'working through the request')
        return []

    def heartbeat(self):
        now = self._now()
        if now - max(self._last_activity, self._last_heartbeat) < 45:
            return None
        self._last_heartbeat = now
        return "I'm still waiting for the next response."

    def finish_sentence(self, tally: Tally, *, exit_code, stopped):
        if stopped:
            return "I've stopped the coding session."
        if exit_code != 0:
            return "I couldn't finish the coding request. I've kept the response for us to check."
        # A process ending successfully proves a response arrived, not that the
        # owner's requested result or all tests were independently verified.
        if tally.changed:
            return "I've received the result and recorded the file changes. I can walk you through them."
        return "I've received the coding response. I can walk you through the result."
