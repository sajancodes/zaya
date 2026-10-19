"""The mobile wire contract: stable, bounded, and free of internal objects."""
import unittest

from core import mobile_protocol as protocol


class StateTests(unittest.TestCase):
    def test_every_documented_state_survives_the_round_trip(self):
        for state in ('STANDBY', 'LISTENING', 'THINKING', 'SPEAKING', 'SLEEPING',
                      'TASK_RUNNING', 'ERROR'):
            self.assertEqual(protocol.normalize_state(state), state)

    def test_internal_states_collapse_onto_the_public_set(self):
        self.assertEqual(protocol.normalize_state('TASK_EXECUTING'), 'TASK_RUNNING')
        self.assertEqual(protocol.normalize_state('task.verifying'), 'TASK_RUNNING')
        self.assertEqual(protocol.normalize_state('idle'), 'STANDBY')
        self.assertEqual(protocol.normalize_state(None), 'STANDBY')
        self.assertEqual(protocol.normalize_state('nonsense'), 'STANDBY')

    def test_emotion_is_never_invented_by_the_phone(self):
        self.assertEqual(protocol.normalize_emotion('HAPPY'), 'happy')
        self.assertEqual(protocol.normalize_emotion('furious'), 'neutral')
        self.assertEqual(protocol.normalize_emotion(None), 'neutral')

    def test_state_envelope_carries_both_authoritative_fields(self):
        envelope = protocol.state_envelope('speaking', 'happy')
        self.assertEqual(envelope['protocol_version'], 1)
        self.assertEqual(envelope['type'], 'zaya.state')
        self.assertEqual(envelope['payload'], {'state': 'SPEAKING', 'emotion': 'happy'})

    def test_priorities_are_named_in_one_direction_only(self):
        self.assertEqual(protocol.priority_name(0), 'critical')
        self.assertEqual(protocol.priority_name(protocol.P1_IMMEDIATE), 'immediate')
        self.assertEqual(protocol.priority_name('nonsense'), 'normal')
        self.assertIn(protocol.P1_IMMEDIATE, protocol.CALL_PRIORITIES)
        self.assertNotIn(protocol.P2_IMPORTANT, protocol.CALL_PRIORITIES)


class BoundsTests(unittest.TestCase):
    def test_long_and_control_character_laden_text_is_clipped(self):
        self.assertEqual(len(protocol.clip('x' * 10000, protocol.LIMITS['caption'])),
                         protocol.LIMITS['caption'])
        self.assertEqual(protocol.clip('a\x00b\x07c', 10), 'abc')
        self.assertEqual(protocol.clip(None, 10), '')

    def test_task_projection_never_leaks_the_whole_record(self):
        task = protocol.normalize_task({
            'id': 'abc', 'goal': 'g' * 5000, 'state': 'executing', 'attempts': '2',
            'evidence': [{'raw': 'secret'}], 'side_effects': [{'summary': 'wrote a file'}],
            'password': 'must-not-appear', 'active_step': 'terminal_exec',
            'error': 'e' * 5000, 'created_at': 1, 'updated_at': 2,
        })
        self.assertEqual(task['task_id'], 'abc')
        self.assertEqual(len(task['goal']), protocol.LIMITS['title'])
        self.assertEqual(len(task['error']), protocol.LIMITS['detail'])
        self.assertEqual(task['attempts'], 2)
        self.assertEqual(task['evidence_count'], 1)
        self.assertEqual(task['side_effect_count'], 1)
        self.assertNotIn('password', task)
        self.assertNotIn('evidence', task)

    def test_unnormalized_task_is_empty_rather_than_broken(self):
        task = protocol.normalize_task(None)
        self.assertEqual(task['task_id'], '')
        self.assertEqual(task['attempts'], 0)


class EventNormalizationTests(unittest.TestCase):
    def test_task_transitions_map_to_the_documented_types(self):
        cases = {
            'task.created': 'task.created', 'task.updated': 'task.updated',
            'task.executing': 'task.updated', 'task.verifying': 'task.updated',
            'task.completed': 'task.completed', 'task.failed': 'task.failed',
            'task.cancelled': 'task.cancelled',
        }
        for internal, expected in cases.items():
            with self.subTest(event=internal):
                events = protocol.normalize_event({'event': internal, 'task': {'id': 't1', 'goal': 'g'}})
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['type'], expected)
                self.assertEqual(events[0]['payload']['task']['task_id'], 't1')

    def test_task_event_without_an_id_is_dropped(self):
        self.assertEqual(protocol.normalize_event({'event': 'task.updated', 'task': {}}), [])

    def test_whatsapp_alert_keeps_untrusted_text_as_bounded_data(self):
        events = protocol.normalize_event({
            'event': 'whatsapp.alert.created', 'chat_id': '123@s.whatsapp.net',
            'alert_id': 'a1', 'title': 'Amma', 'score': 91, 'category': 'urgent',
            'reason': 'x' * 5000,
        })
        payload = events[0]['payload']
        self.assertEqual(events[0]['type'], 'whatsapp.alert.created')
        self.assertEqual(payload['title'], 'Amma')
        self.assertEqual(payload['score'], 91)
        self.assertEqual(len(payload['reason']), protocol.LIMITS['detail'])

    def test_captions_and_messages_become_chat_events(self):
        caption = protocol.normalize_event({'event': 'avatar.caption', 'text': 'Testing the deployment…'})
        self.assertEqual(caption[0]['type'], 'zaya.caption')
        owner = protocol.normalize_event({'event': 'owner.message', 'text': 'check the deploy'})
        self.assertEqual(owner[0]['payload'], {'role': 'user', 'text': 'check the deploy'})
        zaya = protocol.normalize_event({'event': 'zaya.message', 'text': 'It is running.'})
        self.assertEqual(zaya[0]['payload']['role'], 'zaya')

    def test_internal_events_do_not_leak_to_the_phone(self):
        self.assertEqual(protocol.normalize_event({'event': 'avatar.reaction.playing'}), [])
        self.assertEqual(protocol.normalize_event({'event': 'tool.started', 'tool': 'git_control'}), [])
        self.assertEqual(protocol.normalize_event({'event': 'whatsapp.message.sent'}), [])
        self.assertEqual(protocol.normalize_event('not-a-dict'), [])
        self.assertEqual(protocol.normalize_event({}), [])

    def test_system_warning_is_reported_with_its_severity(self):
        events = protocol.normalize_event({'event': 'system.warning', 'severity': 'critical', 'text': 'disk full'})
        self.assertEqual(events[0]['type'], 'system.warning')
        self.assertEqual(events[0]['payload']['severity'], 'critical')

    def test_empty_caption_is_not_sent(self):
        self.assertEqual(protocol.normalize_event({'event': 'avatar.caption', 'text': '   '}), [])


if __name__ == '__main__':
    unittest.main()
