import os
import asyncio
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, 'PYTHONPATH': str(ROOT), 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONIOENCODING': 'utf-8'}
PRIMARY = '''
import os,sys
from pathlib import Path
from PyQt6.QtCore import QCoreApplication,QTimer
from core.single_instance import SingleInstance
app=QCoreApplication(['primary'])
root=Path(sys.argv[2]);guard=SingleInstance(sys.argv[1],root)
if not guard.acquire():
    (root/f'loser-{os.getpid()}').write_text('duplicate blocked')
else:
    guard.on_activate=lambda:(root/'activated').write_text('existing process activated')
    (root/'ready').write_text(str(os.getpid()))
    timer=QTimer();timer.timeout.connect(lambda:app.quit() if (root/'stop').exists() else None);timer.start(30)
    QTimer.singleShot(20000,app.quit)
    try: app.exec()
    finally: guard.close()
'''
SECONDARY = '''
import sys
from PyQt6.QtCore import QCoreApplication
from core.single_instance import SingleInstance
app=QCoreApplication(['secondary'])
guard=SingleInstance(sys.argv[1],sys.argv[2])
assert not guard.acquire(), 'A duplicate acquired the lock'
guard.close()
print('duplicate blocked')
'''


def wait_for(path, processes=(), timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        for process in processes:
            if process.poll() is not None and process.returncode != 0:
                raise AssertionError(process.communicate()[1])
        time.sleep(.025)
    raise AssertionError(f'Timed out waiting for {path.name}')


class SingleInstanceTests(unittest.TestCase):
    def start(self, root, name):
        process = subprocess.Popen([sys.executable, '-u', '-c', PRIMARY, name, str(root)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=ENV)
        return process

    def finish(self, root, processes):
        (root / 'stop').touch()
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)

    def test_duplicate_activates_existing_and_does_not_release_its_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'zaya-test-' + uuid.uuid4().hex
            primary = self.start(root, name)
            try:
                wait_for(root / 'ready', [primary])
                for _ in range(2):
                    result = subprocess.run([sys.executable, '-c', SECONDARY, name, folder], capture_output=True,
                                            text=True, encoding='utf-8', env=ENV, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                wait_for(root / 'activated', [primary])
            finally:
                self.finish(root, [primary])

    def test_main_duplicate_returns_before_constructing_ui_or_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'zaya-test-' + uuid.uuid4().hex
            primary = self.start(root, name)
            try:
                wait_for(root / 'ready', [primary])
                script = '''
import sys
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from core.single_instance import SingleInstance
import main
app=QApplication([])
guard=SingleInstance(sys.argv[1],sys.argv[2])
with patch('core.single_instance.SingleInstance',return_value=guard),patch('main.JarvisUI') as ui,patch('main.JarvisLive') as live:
    main.main()
    ui.assert_not_called();live.assert_not_called()
print('duplicate main did not start UI, microphone or AI')
'''
                result = subprocess.run([sys.executable, '-c', script, name, folder], capture_output=True,
                                        text=True, encoding='utf-8', env=ENV, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                wait_for(root / 'activated', [primary])
            finally:
                self.finish(root, [primary])

    def test_simultaneous_launches_choose_exactly_one_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'zaya-test-' + uuid.uuid4().hex
            processes = [self.start(root, name) for _ in range(4)]
            try:
                wait_for(root / 'ready', processes)
                deadline = time.monotonic() + 8
                while (len(list(root.glob('loser-*'))) < 3 or sum(p.poll() is None for p in processes) > 1) and time.monotonic() < deadline:
                    time.sleep(.025)
                self.assertEqual(len(list(root.glob('loser-*'))), 3)
                self.assertEqual(sum(p.poll() is None for p in processes), 1)
            finally:
                self.finish(root, processes)

    def test_crash_lock_is_recovered_and_clean_close_allows_relaunch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'zaya-test-' + uuid.uuid4().hex
            primary = self.start(root, name)
            wait_for(root / 'ready', [primary])
            # Windows venv executables can be launchers; kill the actual lock
            # owner's PID, rather than leaving its Python child running.
            os.kill(int((root / 'ready').read_text()), signal.SIGTERM)
            primary.communicate(timeout=10)
            (root / 'ready').unlink()
            for _ in range(2):
                (root / 'stop').unlink(missing_ok=True)
                restarted = self.start(root, name)
                try:
                    wait_for(root / 'ready', [restarted])
                    self.assertIsNone(restarted.poll())
                finally:
                    self.finish(root, [restarted])
                (root / 'ready').unlink()

    def test_close_menu_quits_and_runs_audio_and_companion_cleanup(self):
        script = '''
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui import JarvisUI
app=QApplication([]);ui=JarvisUI('face.png');bar=ui._bar;w=ui._win
closed=[];ui.on_shutdown=lambda:closed.append(True)
w._video_audio.setVolume(.6);w._duck_media(True,.2)
assert abs(w._video_audio.volume()-.12)<.001
ui.activate_existing()
assert bar.isVisible() and w.isVisible()
actions={a.text():a for a in bar.context_menu.actions()}
assert 'Settings & Controls' in actions and 'Close Zaya' in actions
QTimer.singleShot(0,actions['Close Zaya'].trigger)
QTimer.singleShot(3000,app.quit)
app.exec()
assert closed==[True] and not bar.isVisible() and not bar.bubble.isVisible()
assert abs(w._video_audio.volume()-.6)<.001
assert bar.tray is None or not bar.tray.isVisible()
print('Close Zaya cleanup OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', env=ENV, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Close Zaya cleanup OK', result.stdout)


class RuntimeShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_cancels_live_connection_without_reconnecting(self):
        from main import JarvisLive
        live = JarvisLive.__new__(JarvisLive)
        live.ui = Mock()
        live._audio_ducker = Mock()
        live._operator_notifications = AsyncMock()
        live._resume_handle = None
        live._enhanced_live = True
        live._session_log = []
        live._build_config = Mock(return_value={})
        entered = asyncio.Event()
        client = MagicMock()

        async def connect():
            entered.set()
            await asyncio.Event().wait()

        client.aio.live.connect.return_value.__aenter__.side_effect = connect
        with patch('main.confirm_gate.bind'), patch('main.set_trim_notifier'), \
                patch('main.audio_devices.configure'), patch('main.audio_devices.prefetch'), \
                patch('dashboard.server.DashboardServer', side_effect=RuntimeError('offline fixture')), \
                patch('main._gemini.live_model', return_value='offline-test'), \
                patch('main._get_api_key', return_value='offline-test'), \
                patch('main.genai.Client', return_value=client), patch('builtins.print'):
            task = asyncio.create_task(live.run())
            await asyncio.wait_for(entered.wait(), timeout=2)
            live.shutdown()
            live.shutdown()  # Both Qt's quit signal and main's finally are safe.
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
        live._audio_ducker.close.assert_called_once()
        client.aio.live.connect.assert_called_once()
