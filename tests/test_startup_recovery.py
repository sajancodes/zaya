import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_unresponsive_connection_times_out_instead_of_waiting_forever(self):
        from main import _connect_live

        class Connection:
            async def __aenter__(self):
                await asyncio.Event().wait()

            async def __aexit__(self, *_):
                pass

        client = Mock()
        client.aio.live.connect.return_value = Connection()
        with patch('main.LIVE_CONNECT_TIMEOUT', .02):
            with self.assertRaises(TimeoutError):
                async with _connect_live(client, 'fixture', {}):
                    self.fail('An unresponsive connection was accepted')


class DesktopStartupTests(unittest.TestCase):
    def test_worker_failure_is_visible_and_saved_without_leaving_thinking_state(self):
        from main import _run_desktop_agent
        ui = Mock()
        with tempfile.TemporaryDirectory() as folder, patch('main.BASE_DIR', Path(folder)), \
                patch('main.JarvisLive', side_effect=RuntimeError('fixture startup failure')):
            _run_desktop_agent(ui, threading.Event())
            ui.set_state.assert_called_with('SLEEPING')
            self.assertIn('could not start', ui.write_log.call_args.args[0])
            self.assertIn('fixture startup failure', (Path(folder) / 'logs/startup_failure.log').read_text())
