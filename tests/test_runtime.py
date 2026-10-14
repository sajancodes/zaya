import unittest
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult
from core.event_bus import EventBus
from core.audit import redact


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = TaskRuntime()

    def tearDown(self):
        self.runtime.db.close()

    def test_completed_side_effect_cannot_repeat(self):
        t = self.runtime.create('push')
        self.runtime.attempt(t.id, 'push')
        self.runtime.finish(t.id, ToolResult('success', 'verified', side_effect=True, evidence=[{'sha': 'abc'}]))
        with self.assertRaises(ValueError):
            self.runtime.attempt(t.id, 'push')
        self.assertEqual(self.runtime.get(t.id).evidence, [{'sha': 'abc'}])

    def test_retry_cap_and_cancellation(self):
        t = self.runtime.create('network')
        for _ in range(3):
            self.runtime.attempt(t.id, 'fetch')
        with self.assertRaises(ValueError):
            self.runtime.attempt(t.id, 'fetch')
        self.runtime.transition(t.id, 'cancelled')
        with self.assertRaises(ValueError):
            self.runtime.transition(t.id, 'executing')

    def test_result_cache_and_unverified_state(self):
        t = self.runtime.create('legacy')
        r = ToolResult('partial', 'Not verified')
        self.runtime.finish(t.id, r)
        self.assertEqual(self.runtime.get(t.id).state, 'waiting_external')
        self.runtime.remember('call-id', r)
        self.assertEqual(self.runtime.cached('call-id'), r)

    def test_event_unsubscribe_and_redaction(self):
        b, events = EventBus(), []
        remove = b.subscribe('*', events.append)
        b.publish('task.created')
        remove()
        b.publish('task.completed')
        self.assertEqual(len(events), 1)
        self.assertEqual(redact({'token': 'private'})['token'], '[REDACTED]')
        self.assertNotIn('abc123', redact('Authorization: Bearer abc123'))
