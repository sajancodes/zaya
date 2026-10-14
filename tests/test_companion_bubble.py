import os
import subprocess
import sys
import unittest
from services.companion_bubble import shorten


class BubbleTests(unittest.TestCase):
    def test_long_text_ends_with_requested_dots(self):
        self.assertEqual(shorten('Hello Zaya'), 'Hello Zaya')
        result = shorten('A long response ' * 30, 100)
        self.assertLessEqual(len(result), 100)
        self.assertTrue(result.endswith('........'))
        self.assertEqual(shorten(' hello\n world  '), 'hello world')

    def test_assistant_stream_and_poke_share_cloud_while_tools_do_not(self):
        script = '''
import json,tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication,QMainWindow
from PyQt6.QtCore import pyqtSignal
from core.zayabar_config import load_config
from services.zayabar import ZayaBar
class Window(QMainWindow):
    _log_sig=pyqtSignal(str)
    _muted=True
    def _toggle_mute(self): pass
app=QApplication([])
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'zayabar.json'
    config=load_config();config['poke_reactions']=[{'text':'Ouch!','audio':''}]
    path.write_text(json.dumps(config))
    bar=ZayaBar(Window(),path)
    bar.show()
    bar.observe_log('Zaya: Hello there!')
    assert bar.bubble.isVisible() and bar.bubble.text=='Hello there!'
    bar.observe_log('TOOL: terminal_exec working')
    assert bar.bubble.text=='Hello there!'
    bar.on_runtime({'event':'avatar.caption','text':'very long reply '*50})
    assert bar.bubble.text.endswith('........')
    assert len(bar.bubble.full_text)>len(bar.bubble.text)
    bar.set_state('THINKING')
    assert bar.bubble.text=='Thinking...'
    bar.play_reaction(0)
    assert bar.bubble.text=='Ouch!'
    screen=app.primaryScreen().availableGeometry()
    assert bar.bubble.x()>=screen.left()
    bar.shutdown()
print('Cloud integration OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Cloud integration OK', result.stdout)
