"""Call policy: the laptop decides, and it never spams the owner.

Every rule here exists to protect one thing: the owner's willingness to answer.
A phone that rings for a completed task, or rings three times about one failed
task, gets silenced — and then the one call that mattered is missed.
"""
import time
import unittest
from unittest.mock import Mock

from core import mobile_protocol as protocol
from core.mobile_bridge import MobileBridge
from core.mobile_calls import (ANSWERED, DECLINED, ENDED, MISSED, RINGING,
                               MobileCallManager, ZayaCall)


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


def manager(**kwargs):
    """A manager with a recording bridge and no real timers."""
    bridge = MobileBridge()
    events: list[dict] = []
    bridge.add_sink(events.append, name='test')
    clock = kwargs.pop('clock', None) or FakeClock()
    ring_timeout = float(kwargs.pop('ring_timeout', 30.0))
    calls = MobileCallManager(bridge, clock=clock, ring_timeout=ring_timeout, **kwargs)
    calls._schedule_ring_timeout = lambda call_id: None      # tests drive the clock
    return calls, bridge, events, clock


def of_type(events, type_):
    return [event for event in events if event['type'] == type_]


class PriorityPolicyTests(unittest.TestCase):
    def test_p0_and_p1_ring_the_phone(self):
        for priority in (protocol.P0_CRITICAL, protocol.P1_IMMEDIATE):
            with self.subTest(priority=priority):
                calls, _bridge, events, _clock = manager()
                call = calls.request_call(title='Now', detail='detail', priority=priority)
                self.assertIsNotNone(call)
                incoming = of_type(events, 'call.incoming')
                self.assertEqual(len(incoming), 1)
                self.assertEqual(incoming[0]['payload']['priority'], priority)
                self.assertEqual(incoming[0]['payload']['priority_name'],
                                 protocol.priority_name(priority))

    def test_p2_becomes_a_notification_and_p3_stays_quiet(self):
        calls, _bridge, events, _clock = manager()
        self.assertIsNone(calls.request_call(title='Failed', priority=protocol.P2_IMPORTANT))
        self.assertIsNone(calls.request_call(title='Finished', priority=protocol.P3_NORMAL))
        self.assertEqual(of_type(events, 'call.incoming'), [])
        self.assertEqual(len(of_type(events, 'system.notify')), 1)     # important only
        notifications = of_type(events, 'notification')
        self.assertEqual(len(notifications), 2)                        # both in the list
        self.assertTrue(notifications[1]['payload']['quiet'])

    def test_a_hostile_priority_cannot_be_escalated_into_a_P0_ring(self):
        calls, _bridge, events, _clock = manager(min_interval=0.0, key_cooldown=0.0)
        call = calls.request_call(title='Urgent', priority=99)
        self.assertEqual(call.priority, protocol.P1_IMMEDIATE)
        self.assertNotEqual(call.priority, protocol.P0_CRITICAL)
        self.assertEqual(of_type(events, 'call.incoming')[0]['payload']['priority_name'],
                         'immediate')
        calls.end(call.call_id)
        self.assertIsNotNone(calls.request_call(title='Stringy', priority='1'))

    # ── suppression ───────────────────────────────────────────────────────────

    def test_a_second_issue_cannot_ring_over_an_active_call(self):
        calls, _bridge, events, _clock = manager()
        first = calls.request_call(title='One', key='k1')
        self.assertIsNotNone(first)
        self.assertIsNone(calls.request_call(title='Two', key='k2'))
        self.assertEqual(len(of_type(events, 'call.incoming')), 1)
        self.assertEqual(calls.suppressed, 1)
        self.assertEqual(len(of_type(events, 'notification')), 1)      # signal kept, ring not

    def test_the_same_problem_does_not_ring_twice_within_the_cooldown(self):
        calls, _bridge, _events, clock = manager(key_cooldown=600.0, min_interval=0.0,
                                                 max_per_hour=99)
        first = calls.request_call(title='Disk full', key='sys:disk')
        self.assertIsNotNone(first)
        self.assertIsNone(calls.request_call(title='Disk full', key='sys:disk'))
        calls.end(first.call_id)                      # the ring ended without an answer
        clock.advance(601.0)
        self.assertIsNotNone(calls.request_call(title='Disk full', key='sys:disk'))

    def test_two_different_problems_still_respect_the_floor_between_calls(self):
        calls, _bridge, _events, clock = manager(min_interval=150.0, key_cooldown=0.0,
                                                 max_per_hour=99)
        first = calls.request_call(title='One', key='a')
        self.assertIsNotNone(first)
        self.assertIsNone(calls.request_call(title='Two', key='b'))
        calls.end(first.call_id)
        clock.advance(151.0)
        self.assertIsNotNone(calls.request_call(title='Two', key='b'))

    def test_the_hourly_cap_holds_even_for_new_problems(self):
        calls, _bridge, _events, clock = manager(min_interval=0.0, key_cooldown=0.0,
                                                 max_per_hour=3)
        for index in range(3):
            call = calls.request_call(title=f'Issue {index}', key=f'k{index}')
            self.assertIsNotNone(call)
            calls.end(call.call_id)
            clock.advance(1.0)
        self.assertIsNone(calls.request_call(title='Issue 4', key='k4'))
        clock.advance(3601.0)
        self.assertIsNotNone(calls.request_call(title='Issue 5', key='k5'))


class RingLifecycleTests(unittest.TestCase):
    def test_answer_marks_the_call_live_and_routes_audio_to_the_phone(self):
        calls, bridge, events, _clock = manager()
        call = calls.request_call(title='Decision needed', detail='Deploy or wait?',
                                 briefing='Ask about the deploy.')
        seen = []
        calls.set_answer_hook(seen.append)
        answered = calls.answer(call.call_id)
        self.assertEqual(answered.state, ANSWERED)
        self.assertTrue(bridge.phone_enabled())
        self.assertTrue(calls.is_answered())
        self.assertEqual([entry.call_id for entry in seen], [call.call_id])
        self.assertEqual(of_type(events, 'call.answered')[0]['payload']['call_id'], call.call_id)

    def test_answering_twice_or_answering_an_ended_call_is_a_no_op(self):
        calls, _bridge, _events, _clock = manager()
        call = calls.request_call(title='One')
        calls.answer(call.call_id)
        self.assertIsNone(calls.answer(call.call_id))
        self.assertIsNotNone(calls.end(call.call_id))
        self.assertIsNone(calls.answer(call.call_id))
        self.assertFalse(calls.is_answered())

    def test_decline_ends_the_call_and_restores_desktop_audio(self):
        calls, bridge, events, _clock = manager()
        bridge.set_output_target('both')
        call = calls.request_call(title='One')
        calls.decline(call.call_id)
        self.assertEqual(bridge.output_target, 'both')
        ended = of_type(events, 'call.ended')
        self.assertEqual(ended[-1]['payload']['outcome'], DECLINED)

    def test_a_ring_that_is_never_answered_becomes_one_missed_call_with_a_summary(self):
        calls, _bridge, events, _clock = manager()
        call = calls.request_call(title='Task needs your decision', detail='Deploy the API',
                                  reason='A task is waiting for the owner.')
        self.assertEqual(call.state, RINGING)
        missed = calls.miss(call.call_id)
        self.assertEqual(missed.state, MISSED)
        payload = of_type(events, 'call.missed')[-1]['payload']
        self.assertEqual(payload['summary'], 'Deploy the API')
        self.assertEqual(payload['call_id'], call.call_id)
        # One written notification, and no second ring — ever.
        self.assertEqual(len(of_type(events, 'call.incoming')), 1)
        self.assertIsNone(calls.miss(call.call_id))
        self.assertEqual(len(of_type(events, 'call.missed')), 1)

    def test_a_missed_call_does_not_block_the_next_real_problem(self):
        calls, _bridge, _events, clock = manager(min_interval=150.0, key_cooldown=0.0)
        first = calls.request_call(title='One', key='a')
        calls.miss(first.call_id)
        clock.advance(151.0)
        self.assertIsNotNone(calls.request_call(title='Two', key='b'))

    def test_a_call_created_when_the_phone_is_silent_still_expires_safely(self):
        calls, _bridge, _events, _clock = manager(ring_timeout=5.0)
        call = calls.request_call(title='One')
        calls._ring_expired(call.call_id)
        self.assertEqual(calls.recent(1)[0]['state'], MISSED)

    def test_the_oldest_calls_are_trimmed_from_memory(self):
        calls, _bridge, _events, clock = manager(min_interval=0.0, key_cooldown=0.0,
                                                 max_per_hour=10_000)
        for index in range(60):
            call = calls.request_call(title=f'Issue {index}', key=f'k{index}')
            calls.end(call.call_id)
            clock.advance(1.0)
        self.assertLessEqual(len(calls.recent(200)), len(calls._order))
        self.assertLessEqual(len(calls._order), 40)


class BusPolicyTests(unittest.TestCase):
    def test_a_critical_warning_is_P0_and_an_error_is_only_a_notification(self):
        calls, _bridge, events, _clock = manager()
        calls.handle_event({'event': 'system.warning', 'severity': 'critical', 'text': 'Disk failure'})
        calls.handle_event({'event': 'system.warning', 'severity': 'high', 'text': 'Camera busy'})
        incoming = of_type(events, 'call.incoming')
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]['payload']['priority'], protocol.P0_CRITICAL)
        self.assertEqual(len(of_type(events, 'system.notify')), 1)
        self.assertIn('Camera busy', of_type(events, 'notification')[0]['payload']['body'])

    def test_a_failed_task_with_side_effects_rings_but_a_plain_failure_notifies(self):
        calls, _bridge, events, _clock = manager()
        calls.handle_event({'event': 'task.failed', 'task': {
            'id': 't1', 'goal': 'Migrate the database', 'state': 'failed',
            'side_effects': [{'summary': 'dropped a column'}]}})
        calls.handle_event({'event': 'task.failed', 'task': {
            'id': 't2', 'goal': 'Fetch the news', 'state': 'failed', 'attempts': 1, 'max_attempts': 3}})
        calls.handle_event({'event': 'task.completed', 'task': {
            'id': 't3', 'goal': 'Clear the desk', 'state': 'completed'}})
        incoming = of_type(events, 'call.incoming')
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]['payload']['source'], 'task')
        self.assertIn('Migrate the database', incoming[0]['payload']['detail'])
        # The spoken briefing stays on the laptop; it is a script, not phone data.
        self.assertNotIn('briefing', incoming[0]['payload'])
        self.assertEqual(len(of_type(events, 'system.notify')), 1)      # plain failure only
        self.assertEqual(len(of_type(events, 'notification')), 2)       # failure + completion

    def test_a_waiting_task_rings_once_and_asks_for_a_decision(self):
        calls, _bridge, events, _clock = manager()
        calls.handle_event({'event': 'task.waiting_confirmation', 'task': {
            'id': 't9', 'goal': 'Delete the old backups', 'state': 'waiting_confirmation'}})
        calls.handle_event({'event': 'task.waiting_confirmation', 'task': {
            'id': 't9', 'goal': 'Delete the old backups', 'state': 'waiting_confirmation'}})
        incoming = of_type(events, 'call.incoming')
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]['payload']['source'], 'task')
        self.assertIn('Delete the old backups', incoming[0]['payload']['detail'])

    def test_an_urgent_message_rings_and_a_normal_one_does_not(self):
        calls, _bridge, events, _clock = manager(key_cooldown=0.0, min_interval=0.0)
        calls.handle_event({'event': 'whatsapp.alert.created', 'alert_id': 'a1', 'title': 'Amma',
                            'score': 90, 'category': 'urgent', 'reason': 'Call me now'})
        self.assertEqual(len(of_type(events, 'call.incoming')), 1)
        calls.handle_event({'event': 'whatsapp.alert.created', 'alert_id': 'a2', 'title': 'Office',
                            'score': 72, 'category': 'work', 'reason': 'Needs a reply'})
        self.assertEqual(len(of_type(events, 'call.incoming')), 1)
        self.assertEqual(len(of_type(events, 'notification')), 1)

    def test_a_remote_confirmation_rings_the_desktop_because_the_owner_is_away(self):
        calls, _bridge, events, _clock = manager()
        calls.handle_event({'event': 'confirm.requested', 'title': 'Delete branch main',
                            'detail': 'twice', 'key': 'confirm:1', 'remote': True})
        incoming = of_type(events, 'call.incoming')
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]['payload']['source'], 'confirm')
        self.assertIn('Confirm on the desktop', incoming[0]['payload']['title'])

    def test_a_local_confirmation_is_only_written_down(self):
        calls, _bridge, events, _clock = manager()
        calls.handle_event({'event': 'confirm.requested', 'title': 'Delete branch main',
                            'remote': False})
        self.assertEqual(of_type(events, 'call.incoming'), [])
        self.assertEqual(len(of_type(events, 'notification')), 1)

    def test_a_replayed_bus_event_never_crashes_the_policy(self):
        calls, _bridge, _events, _clock = manager()
        for event in ({'event': 'task.failed'}, {'event': 'whatsapp.alert.created'},
                      {'event': 'system.warning', 'severity': 'critical'},
                      {'event': 'call.requested'}, {'event': 'unknown.event'}, {}):
            with self.subTest(event=event.get('event', '')):
                calls.handle_event(event)


if __name__ == '__main__':
    unittest.main()
