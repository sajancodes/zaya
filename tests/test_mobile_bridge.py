"""The bridge fans Zaya's state and voice out without ever slowing her down.

Two failure modes are pinned here: one broken phone taking the local session or
the other phones with it, and an unbounded audio queue growing a latency tail.
"""
import threading
import unittest

from core import mobile_protocol as protocol
from core.mobile_bridge import (AUDIO_QUEUE_BYTES, AUDIO_QUEUE_SECONDS, AudioListener,
                                MobileBridge)


def recorder():
    events = []

    def sink(envelope):
        events.append(envelope)

    return events, sink


class SinkIsolationTests(unittest.TestCase):
    def test_one_broken_sink_leaves_the_others_working(self):
        bridge = MobileBridge()
        good, sink = recorder()

        def broken(envelope):
            raise RuntimeError('phone gone')

        bridge.add_sink(broken, name='wedged')
        bridge.add_sink(sink, name='healthy')
        with self.assertLogs('core.mobile_bridge', level='WARNING'):
            self.assertEqual(bridge.emit(protocol.envelope('pong', {})), 1)
        self.assertEqual(len(good), 1)
        self.assertEqual(bridge.sink_failures, 1)
        self.assertIn('wedged', bridge.last_failure)

    def test_detached_sink_stops_receiving(self):
        bridge = MobileBridge()
        events, sink = recorder()
        detach = bridge.add_sink(sink, name='phone')
        bridge.broadcast('pong')
        detach()
        bridge.broadcast('pong')
        self.assertEqual(len(events), 1)
        self.assertEqual(bridge.sink_count(), 0)


class StateTests(unittest.TestCase):
    def test_state_is_announced_only_when_it_changes(self):
        bridge = MobileBridge()
        events, sink = recorder()
        bridge.add_sink(sink)
        bridge.set_state('THINKING')
        bridge.set_state('thinking')                  # same state, no second event
        self.assertEqual([event['type'] for event in events], ['zaya.state'])
        self.assertEqual(events[0]['payload'], {'state': 'THINKING', 'emotion': 'neutral'})
        self.assertEqual(bridge.state, 'THINKING')

    def test_emotion_change_republishes_a_coherent_state(self):
        bridge = MobileBridge()
        bridge.set_state('SPEAKING', announce=False)
        events, sink = recorder()
        bridge.add_sink(sink)
        bridge.set_emotion('HAPPY')
        self.assertEqual(events[0]['payload'], {'state': 'SPEAKING', 'emotion': 'happy'})
        self.assertEqual(bridge.emotion, 'happy')

    def test_caption_is_clipped_deduplicated_and_skipped_when_empty(self):
        bridge = MobileBridge()
        events, sink = recorder()
        bridge.add_sink(sink)
        bridge.caption('One moment.')
        bridge.caption('One moment.')
        bridge.caption('   ')
        bridge.caption('x' * 5000)
        self.assertEqual([event['type'] for event in events],
                         ['zaya.caption', 'zaya.caption'])
        self.assertEqual(len(events[1]['payload']['text']), protocol.LIMITS['caption'])

    def test_bus_events_become_protocol_envelopes(self):
        bridge = MobileBridge()
        events, sink = recorder()
        bridge.add_sink(sink)
        bridge.handle_event({'event': 'zaya.state.changed', 'state': 'LISTENING'})
        bridge.handle_event({'event': 'avatar.emotion', 'emotion': 'happy'})
        bridge.handle_event({'event': 'task.completed', 'task': {'id': 't1', 'goal': 'deploy'}})
        self.assertEqual([event['type'] for event in events],
                         ['zaya.state', 'zaya.state', 'task.completed'])

    def test_a_broken_event_never_raises_into_the_bus(self):
        class Hostile:
            def __str__(self):
                raise ValueError('cannot be stringified')

        bridge = MobileBridge()
        events, sink = recorder()
        bridge.add_sink(sink)
        with self.assertLogs('core.mobile_bridge', level='ERROR'):
            bridge.handle_event({'event': 'avatar.caption', 'text': Hostile()})
        bridge.handle_event({'event': 'task.updated', 'task': Hostile()})
        bridge.handle_event('not-a-dict')
        self.assertEqual(events, [])                   # nothing invented, nothing raised

    def test_snapshot_is_the_first_paint_of_a_phone(self):
        bridge = MobileBridge()
        bridge.set_state('TASK_RUNNING', announce=False)
        bridge.set_emotion('happy', announce=False)
        bridge.caption('Working on it.')
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot['state'], 'TASK_RUNNING')
        self.assertEqual(snapshot['emotion'], 'happy')
        self.assertEqual(snapshot['caption'], 'Working on it.')
        self.assertEqual(snapshot['output_target'], 'desktop')
        self.assertFalse(snapshot['call_active'])


class OutputRoutingTests(unittest.TestCase):
    def test_only_known_targets_are_accepted(self):
        bridge = MobileBridge()
        for target in ('desktop', 'phone', 'both'):
            self.assertEqual(bridge.set_output_target(target), target)
        with self.assertRaises(ValueError):
            bridge.set_output_target('speakerphone')
        self.assertEqual(bridge.output_target, 'both')

    def test_a_call_moves_the_voice_to_the_phone_and_restores_it_afterwards(self):
        bridge = MobileBridge()
        bridge.set_output_target('both')
        bridge.set_call_active(True)
        self.assertEqual(bridge.output_target, 'phone')
        self.assertTrue(bridge.phone_enabled())
        self.assertFalse(bridge.desktop_enabled())
        bridge.set_call_active(False)
        self.assertEqual(bridge.output_target, 'both')

    def test_output_changes_reach_the_phone(self):
        bridge = MobileBridge()
        events, sink = recorder()
        bridge.add_sink(sink)
        bridge.set_output_target('phone')
        self.assertEqual(events[-1]['type'], 'system.output')
        self.assertEqual(events[-1]['payload']['target'], 'phone')


class AudioListenerTests(unittest.TestCase):
    def test_frames_are_dropped_oldest_first_instead_of_growing(self):
        listener = AudioListener('phone', maxlen=4)
        for index in range(10):
            listener.push(f'frame-{index}'.encode())
        self.assertEqual(listener.pending(), 4)
        self.assertEqual(listener.drain(), [b'frame-6', b'frame-7', b'frame-8', b'frame-9'])
        self.assertEqual(listener.dropped, 6)
        self.assertEqual(listener.delivered, 4)

    def test_closed_listeners_accept_nothing(self):
        listener = AudioListener('phone', maxlen=4)
        listener.close()
        listener.push(b'frame')
        self.assertEqual(listener.pending(), 0)

    def test_audio_only_reaches_the_phone_when_the_phone_is_a_target(self):
        bridge = MobileBridge()
        listener = bridge.add_audio_listener('out')
        self.assertEqual(bridge.push_output_audio(b'pcm'), 0)   # desktop-only default
        self.assertEqual(listener.pending(), 0)
        bridge.set_output_target('phone')
        self.assertEqual(bridge.push_output_audio(b'pcm'), 1)
        self.assertEqual(listener.pending(), 1)

    def test_detached_listener_stops_receiving_immediately(self):
        bridge = MobileBridge()
        first = bridge.add_audio_listener('first')
        second = bridge.add_audio_listener('second')
        bridge.set_output_target('phone')
        bridge.push_output_audio(b'one')
        bridge.remove_audio_listener(first)
        bridge.push_output_audio(b'two')
        self.assertEqual(first.pending(), 0)
        self.assertEqual(second.drain(), [b'one', b'two'])
        self.assertEqual(bridge.audio_listener_count(), 1)

    def test_the_backlog_is_bounded_by_seconds_of_audio_not_frame_count(self):
        # Both bounds exist because a batch is up to 200 ms while a browser chunk
        # is ~43 ms. 5 s at 24 kHz mono PCM16 is 240 000 bytes.
        self.assertEqual(AUDIO_QUEUE_SECONDS, 5.0)
        self.assertEqual(AUDIO_QUEUE_BYTES, 5 * 24000 * 2)

        listener = AudioListener('phone')
        for _ in range(50):                        # 50 × 200 ms = 10 s offered
            listener.push(b'\x00' * 9600)
        self.assertLessEqual(listener.pending_bytes(), AUDIO_QUEUE_BYTES)
        self.assertLessEqual(listener.pending() * 0.2, AUDIO_QUEUE_SECONDS)
        self.assertGreater(listener.dropped, 0)

    def test_small_frames_are_kept_and_never_undercut_by_the_byte_budget(self):
        listener = AudioListener('phone', maxlen=4, max_bytes=1000)
        listener.push(b'x' * 300)
        self.assertEqual(listener.pending(), 1)     # never evicted to empty
        listener.push(b'x' * 300)
        listener.push(b'x' * 300)
        listener.push(b'x' * 300)
        self.assertLessEqual(listener.pending_bytes(), 1000)
        self.assertEqual(listener.pending(), 3)     # 3 × 300 B fits; the oldest went

    def test_a_stopped_consumer_loop_does_not_break_the_push_path(self):
        class DeadLoop:
            def call_soon_threadsafe(self, fn):
                raise RuntimeError('loop closed')

        listener = AudioListener('phone')
        listener.bind(DeadLoop(), threading.Event())
        listener.push(b'pcm')                     # must not raise into the audio path
        self.assertTrue(listener.closed)


if __name__ == '__main__':
    unittest.main()
