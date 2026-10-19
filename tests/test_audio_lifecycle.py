"""Audio discovery and helper sessions have one bounded owner at a time."""
import asyncio
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core import audio_devices, gemini


class DiscoveryTests(unittest.TestCase):
    def test_parallel_first_open_probes_once_and_publishes_a_complete_snapshot(self):
        def query():
            time.sleep(.02)
            audio_devices._chosen_api.update(input='fixture', output='fixture')
            return {'input': ['Fixture microphone'], 'output': ['Fixture speaker']}

        with patch.object(audio_devices, '_cache', None), \
                patch.object(audio_devices, '_chosen_api', {}), \
                patch.object(audio_devices, '_query', side_effect=query) as discover:
            with ThreadPoolExecutor(max_workers=8) as workers:
                results = list(workers.map(lambda _: audio_devices.list_devices('input'), range(16)))
            discover.assert_called_once()
            self.assertTrue(all(result == ['Fixture microphone'] for result in results))
            self.assertEqual(audio_devices._chosen_api['input'], 'fixture')

    def test_rate_change_invalidates_transport_results_and_device_selection_together(self):
        with patch.object(audio_devices, '_cache', {'input': ['old']}), \
                patch.object(audio_devices, '_RATES', {}), \
                patch.object(audio_devices, '_chosen_api', {'input': 'old'}), \
                patch.object(audio_devices, '_probe_results', {'old': True}):
            audio_devices.configure(input_rate=48000, output_rate=48000)
            self.assertIsNone(audio_devices._cache)
            self.assertEqual(audio_devices._probe_results, {})
            self.assertEqual(audio_devices._chosen_api, {'input': None, 'output': None})
            self.assertEqual(audio_devices._RATES, {'input': 48000, 'output': 48000})


class LiveHelperLifecycleTests(unittest.TestCase):
    def test_deadline_cancels_live_coroutine_and_releases_slot_only_after_worker_exit(self):
        entered, stopped = threading.Event(), threading.Event()
        real_thread = threading.Thread
        slots = threading.BoundedSemaphore(1)

        async def stalled(*_):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        class DeadlineThread:
            def __init__(self, **kwargs):
                self.worker = real_thread(**kwargs)
            def start(self):
                self.worker.start()
            def join(self, timeout):
                # Simulate the deadline, without waiting 30 seconds in CI.
                if not entered.wait(2):
                    raise AssertionError('Helper never entered the coroutine')
            def is_alive(self):
                return self.worker.is_alive()

        with patch.object(gemini, '_LIVE_SLOTS', slots), \
                patch.object(gemini, '_to_live_parts', return_value=['fixture']), \
                patch.object(gemini, '_live_turn', stalled), \
                patch.object(gemini.threading, 'Thread', DeadlineThread):
            with self.assertRaises(TimeoutError):
                gemini._live_call('fixture', None, 1000, 'fixture-key')
            self.assertTrue(stopped.wait(2), 'Timed-out Live coroutine was not cancelled')
            self.assertTrue(slots.acquire(timeout=2), 'Worker did not return its session slot')
            slots.release()

    def test_thread_creation_failure_returns_the_reserved_slot(self):
        slots = threading.BoundedSemaphore(1)
        with patch.object(gemini, '_LIVE_SLOTS', slots), \
                patch.object(gemini, '_to_live_parts', return_value=['fixture']), \
                patch.object(gemini.threading, 'Thread', side_effect=RuntimeError('fixture spawn error')):
            with self.assertRaises(RuntimeError):
                gemini._live_call('fixture', None, 1000, 'fixture-key')
        self.assertTrue(slots.acquire(blocking=False))
        slots.release()
