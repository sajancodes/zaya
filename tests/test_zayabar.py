import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from core.zayabar_config import CONFIG_PATH, load_config, asset_path


class BarConfigTests(unittest.TestCase):
    def test_paths_defaults_and_emotion_fallback(self):
        config = load_config()
        config['assets'] = {'standby': '', 'thinking': '', 'poked': '', 'talking': {}}
        self.assertTrue(config['enabled'])
        self.assertIsNone(asset_path(config, 'standby'))
        config['assets']['standby'] = 'images/rest.gif'
        self.assertEqual(asset_path(config, 'thinking'), CONFIG_PATH.parent / 'images/rest.gif')
        config['assets']['talking']['neutral'] = 'images/speak.png'
        self.assertEqual(asset_path(config, 'talking', 'happy'), CONFIG_PATH.parent / 'images/speak.png')

    def test_invalid_config_does_not_replace_a_working_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'zayabar.json'
            path.write_text(json.dumps({'height': -10}))
            with self.assertRaises(ValueError):
                load_config(path)
            path.write_text(json.dumps({'enabled': 'false'}))
            with self.assertRaises(ValueError):
                load_config(path)


class BarIntegrationTests(unittest.TestCase):
    def test_real_media_states_reactions_and_right_click(self):
        script = r'''
import json, tempfile
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtTest import QTest
from core.zayabar_config import load_config
from services.zayabar import ZayaBar
class Window(QMainWindow):
    _log_sig = pyqtSignal(str)
    def _toggle_mute(self): pass
app = QApplication([])
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    a = Image.new('RGBA', (100,100), (255,0,0,255))
    b = Image.new('RGBA', (100,100), (0,0,255,255))
    a.save(root/'standby.gif', save_all=True, append_images=[b], duration=80, loop=0)
    b.save(root/'thinking.png')
    config = load_config()
    config['poke_reactions'] = []
    config['assets']['standby'] = str(root/'standby.gif')
    config['assets']['thinking'] = str(root/'thinking.png')
    path = root/'zayabar.json'
    path.write_text(json.dumps(config))
    main = Window()
    bar = ZayaBar(main, path)
    bar.show()
    QTest.qWait(180)
    assert bar.movie is not None and not bar.frame.isNull()
    assert bar.geometry().bottom() <= app.primaryScreen().geometry().bottom()
    bar.state_changed.emit('THINKING')
    app.processEvents()
    assert bar.mode == 'thinking' and bar.movie is None
    assert bar.frame.toImage().pixelColor(50,50).blue() == 255
    bar.state_changed.emit('SPEAKING')
    app.processEvents()
    assert bar.mode == 'talking'
    bar.config['assets']['talking']['neutral'] = str(root/'thinking.png')
    bar.config['assets']['talking']['sad'] = str(root/'missing.png')
    bar.on_runtime({'event':'avatar.emotion','emotion':'sad'})
    assert not bar.frame.isNull() and bar.frame.toImage().pixelColor(50,50).blue()==255
    bar.on_runtime({'event':'avatar.emotion','emotion':'happy'})
    assert bar.emotion == 'happy'
    bar.state_changed.emit('LISTENING')
    seen=[]
    bar.reaction_requested.connect(seen.append)
    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton)
    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton)
    assert bar.mode == 'poked' and len(seen)==1
    bar.poked_until = 0
    bar.state_changed.emit('LISTENING')
    assert bar.mode == 'standby'
    bar.on_runtime({'event':'task.updated','task':{'id':'one','state':'executing'}})
    assert bar.mode == 'thinking'
    bar.on_runtime({'event':'task.updated','task':{'id':'one','state':'completed'}})
    assert bar.mode == 'standby'
    bar.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, bar.rect().center()))
    assert main.isVisible()
    path.write_text('{bad json')
    assert bar.reload_config() is False and bar.config['assets']['standby'].endswith('standby.gif')
    bar.shutdown()
    main.close()
print('Companion integration OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Companion integration OK', result.stdout)

    def test_main_ui_starts_bar_and_keeps_existing_window_accessible(self):
        script = '''
from PyQt6.QtWidgets import QApplication
from ui import JarvisUI
app = QApplication([])
ui = JarvisUI('face.png')
assert ui._bar is not None and ui._bar.isVisible()
ui.set_state('SPEAKING')
app.processEvents()
assert ui._bar.mode == 'talking'
ui._bar.open_main_window()
assert ui._win.isVisible()
assert ui._win._title_lbl.text() == 'ZAYA'
ui._win.close()
assert ui._bar.isVisible()
ui._bar.open_main_window()
assert ui._win.isVisible()
ui._bar.shutdown()
ui._win._unsubscribe_runtime()
ui._win.close()
print('Main UI integration OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Main UI integration OK', result.stdout)

    def test_disabled_bar_preserves_original_startup(self):
        script = '''
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from ui import JarvisUI
from core.zayabar_config import load_config
app = QApplication([])
config = load_config()
config['enabled'] = False
with patch('core.zayabar_config.load_config', return_value=config):
    ui = JarvisUI('face.png')
assert ui._bar is None and ui._win.isVisible()
assert app.quitOnLastWindowClosed()
ui._win._unsubscribe_runtime()
ui._win.close()
print('Original startup OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Original startup OK', result.stdout)
