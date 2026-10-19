"""A remote command gets its own owner scope, and it only ever runs once.

The bug this suite pins down: a dashboard command used to inherit whatever owner
scope the laptop had last set, so the operator's cached tool results
(`scope:tool:args`) could answer a brand-new phone command, and a retried request
could execute twice.
"""
import asyncio
from collections import deque
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from core.execution_policy import TRUST_AUTHENTICATED_REMOTE_OWNER, TRUST_LOCAL_OWNER
from core.remote_commands import (ACKNOWLEDGED, COMPLETED, EXECUTING, FAILED, SUBMITTED,
                                  RemoteCommandGate)

from main import JarvisLive


class GateTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000.0]
        self.gate = RemoteCommandGate(clock=lambda: self.clock[0])

    def test_every_accepted_command_gets_its_own_scope(self):
        first, first_outcome = self.gate.submit('check the deploy', source='phone')
        second, second_outcome = self.gate.submit('check the deploy', source='phone')
        self.assertEqual((first_outcome, second_outcome), ('accepted', 'duplicate'))
        self.assertIs(first, second)                    # the resend maps to the original
        self.clock[0] += 10.0
        third, third_outcome = self.gate.submit('check the deploy', source='phone')
        self.assertEqual(third_outcome, 'accepted')
        self.assertNotEqual(first.scope, third.scope)
        self.assertNotEqual(first.request_id, third.request_id)

    def test_a_resend_with_the_same_request_id_is_never_run_twice(self):
        command, outcome = self.gate.submit('deploy', request_id='abc123', source='phone')
        self.assertEqual(outcome, 'accepted')
        again, outcome = self.gate.submit('deploy', request_id='abc123', source='phone')
        self.assertEqual(outcome, 'duplicate')
        self.assertIs(again, command)
        self.gate.acknowledge('abc123')
        replay, outcome = self.gate.submit('deploy', request_id='abc123', source='phone')
        self.assertEqual(outcome, 'duplicate')
        self.assertEqual(replay.status, ACKNOWLEDGED)   # the replay learns the real state
        self.assertEqual(self.gate.stats()['accepted'], 1)
        self.assertEqual(self.gate.stats()['duplicates'], 2)

    def test_the_text_window_is_short_and_never_crosses_transports(self):
        self.gate.submit('status', source='phone')
        _twin, outcome = self.gate.submit('status', source='phone')
        self.assertEqual(outcome, 'duplicate')
        _other, outcome = self.gate.submit('status', source='dashboard')
        self.assertEqual(outcome, 'accepted')           # a different client is a new ask
        self.clock[0] += 3.0
        _later, outcome = self.gate.submit('status', source='phone')
        self.assertEqual(outcome, 'accepted')

    def test_empty_text_is_rejected_without_creating_a_record(self):
        command, outcome = self.gate.submit('   ', source='phone')
        self.assertIsNone(command)
        self.assertEqual(outcome, 'rejected')
        self.assertEqual(self.gate.stats()['accepted'], 0)

    def test_the_lifecycle_is_explicit_and_monotonic(self):
        command, _ = self.gate.submit('deploy', source='phone')
        self.assertEqual(command.status, SUBMITTED)
        self.assertEqual(self.gate.acknowledge(command.request_id).status, ACKNOWLEDGED)
        self.assertEqual(self.gate.begin(command.request_id).status, EXECUTING)
        done = self.gate.complete(command.request_id)
        self.assertEqual(done.status, COMPLETED)
        self.assertEqual(done.updated_at, self.clock[0])

    def test_failure_keeps_the_reason_for_the_phone(self):
        command, _ = self.gate.submit('deploy', source='phone')
        failed = self.gate.complete(command.request_id, ok=False, error='Zaya is offline')
        self.assertEqual(failed.status, FAILED)
        self.assertEqual(failed.envelope()['payload']['error'], 'Zaya is offline')
        self.assertEqual(failed.envelope()['type'], 'command.status')
        self.assertEqual(failed.envelope()['protocol_version'], 1)

    def test_unknown_request_ids_are_ignored_instead_of_created(self):
        self.assertIsNone(self.gate.begin('nope'))
        self.assertIsNone(self.gate.acknowledge('nope'))
        self.assertIsNone(self.gate.complete('nope'))

    def test_old_commands_are_forgotten_so_the_gate_cannot_grow_forever(self):
        gate = RemoteCommandGate(ttl=5.0, history=3, dedupe_window=0.0)
        for index in range(6):
            gate.submit(f'command {index}', source='phone')
        self.assertLessEqual(gate.stats()['tracked'], 3)

    def test_a_stale_ping_of_an_expired_request_is_a_new_command(self):
        gate = RemoteCommandGate(ttl=5.0, clock=lambda: self.clock[0])
        gate.submit('deploy', request_id='abc', source='phone')
        self.clock[0] += 6.0
        _command, outcome = gate.submit('deploy', request_id='abc', source='phone')
        self.assertEqual(outcome, 'accepted')


class DashboardIntakeTests(unittest.TestCase):
    """dashboard/server.py must queue exactly one item per accepted request."""

    def setUp(self):
        from dashboard.server import DashboardServer
        self.server = DashboardServer.__new__(DashboardServer)      # no FastAPI needed
        self.server._command_queue = asyncio.Queue(maxsize=2)
        self.server._wake_callback = None

    def test_an_accepted_command_carries_its_request_id_and_scope(self):
        command, outcome = self.server.submit_remote_command('deploy it', source='phone',
                                                             request_id='rid-1')
        self.assertEqual(outcome, 'accepted')
        item = self.server._command_queue.get_nowait()
        self.assertEqual(item['text'], 'deploy it')
        self.assertEqual(item['request_id'], 'rid-1')
        self.assertEqual(item['source'], 'phone')
        self.assertEqual(item['scope'], command.scope)
        self.assertTrue(item['scope'])

    def test_a_replayed_request_id_queues_nothing_new(self):
        self.server.submit_remote_command('deploy it', source='phone', request_id='rid-2')
        _command, outcome = self.server.submit_remote_command('deploy it', source='phone',
                                                              request_id='rid-2')
        self.assertEqual(outcome, 'duplicate')
        self.assertEqual(self.server._command_queue.qsize(), 1)

    def test_a_busy_laptop_rejects_the_command_and_says_so(self):
        self.server.submit_remote_command('one', source='phone', request_id='r1')
        self.server.submit_remote_command('two', source='phone', request_id='r2')
        command, outcome = self.server.submit_remote_command('three', source='phone',
                                                            request_id='r3')
        self.assertEqual(outcome, 'rejected')
        self.assertEqual(command.status, 'failed')
        self.assertEqual(command.error, 'Zaya was busy.')


def command_agent():
    """A JarvisLive with only the attributes the command relay touches."""
    live = JarvisLive.__new__(JarvisLive)
    live.ui = Mock()
    live.session = SimpleNamespace()
    live._wake_enabled = False
    live._awake = True
    live._owner_activity = Mock()
    live._conversation = None
    live._dashboard = SimpleNamespace(_command_queue=asyncio.Queue(maxsize=8))
    live._send_owner_text = AsyncMock()
    live._pending_remote = deque(maxlen=8)
    return live


class CommandRelayTests(unittest.IsolatedAsyncioTestCase):
    async def _drain(self, live):
        task = asyncio.create_task(live._process_dashboard_commands())
        try:
            for _ in range(100):
                await asyncio.sleep(0.01)
                if live._send_owner_text.await_count:
                    break
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def test_a_phone_command_opens_its_own_scope_with_remote_owner_trust(self):
        from core.remote_commands import get_gate
        live = command_agent()
        get_gate().submit('check the deploy', request_id='relay-1', source='phone')
        live._dashboard._command_queue.put_nowait({
            'text': 'check the deploy', 'request_id': 'relay-1',
            'source': 'phone', 'scope': 'scope-from-the-phone',
        })
        await self._drain(live)
        self.assertEqual(live._operator_scope, 'scope-from-the-phone')
        self.assertEqual(live._operator_trust, TRUST_AUTHENTICATED_REMOTE_OWNER)
        self.assertNotEqual(live._operator_trust, TRUST_LOCAL_OWNER)
        self.assertIn('relay-1', list(live._pending_remote))
        self.assertEqual(get_gate().get('relay-1').status, ACKNOWLEDGED)
        live._send_owner_text.assert_awaited_once_with('check the deploy')

    async def test_legacy_plain_text_still_runs_with_a_fresh_scope(self):
        live = command_agent()
        live._dashboard._command_queue.put_nowait('turn off the lights')
        await self._drain(live)
        self.assertTrue(live._operator_scope)
        self.assertEqual(live._operator_trust, TRUST_AUTHENTICATED_REMOTE_OWNER)
        live._send_owner_text.assert_awaited_once_with('turn off the lights')

    async def test_no_session_fails_the_request_instead_of_hanging_it(self):
        from core.remote_commands import get_gate
        live = command_agent()
        live.session = None
        get_gate().submit('deploy', request_id='relay-nosession', source='phone')
        live._dashboard._command_queue.put_nowait({
            'text': 'deploy', 'request_id': 'relay-nosession', 'source': 'phone',
            'scope': 'scope-x',
        })
        task = asyncio.create_task(live._process_dashboard_commands())
        try:
            for _ in range(200):
                await asyncio.sleep(0.05)
                status = get_gate().get('relay-nosession').status
                if status == FAILED:
                    break
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.assertEqual(get_gate().get('relay-nosession').status, FAILED)
        self.assertIn('session', get_gate().get('relay-nosession').error.lower())
        self.assertEqual(live._send_owner_text.await_count, 0)


if __name__ == '__main__':
    unittest.main()
