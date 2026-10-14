import os
from pathlib import Path
import subprocess
import sys
import unittest


class AppIntegrationTests(unittest.TestCase):
    def test_ui_boot_identity_and_task_signal(self):
        script = '''
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase
from pathlib import Path
import os
app=QApplication([])
if not QFontDatabase.families() and os.name == 'nt':
    fonts=Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
    for name in ['cour.ttf', 'segoeui.ttf']:
        if (fonts/name).exists(): QFontDatabase.addApplicationFont(str(fonts/name))
from ui import MainWindow
w=MainWindow('face.png')
w.show()
w._activity_sig.emit('Git operation · verifying')
app.processEvents()
assert w._title_lbl.text() == 'ZAYA'
assert w._sub_lbl.text() == 'Built by Sajan Rai'
assert w._activity_lbl.text() == 'Git operation · verifying'
assert w._title_lbl.geometry().top() >= 0
assert w._activity_lbl.geometry().bottom() <= w._title_lbl.parentWidget().height()
w._unsubscribe_runtime()
w.close()
print('UI smoke OK')
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parent.parent,
                                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}, capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('UI smoke OK', result.stdout)

    def test_application_import_and_complete_live_schema(self):
        script = '''
import main
from unittest.mock import patch
from core.action_loader import ActionRegistry
from core.plugin_loader import PluginRegistry
agent=main.JarvisLive.__new__(main.JarvisLive)
agent._resume_handle=None
agent._enhanced_live=True
agent._tuned_live=True
agent._action_registry=ActionRegistry({},print)
agent._plugin_registry=PluginRegistry({},print)
with patch.object(main,'load_memory',return_value={}): config=agent._build_config()
assert 'built by Sajan Rai' in config.system_instruction
assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == 'Nika'
assert not config.thinking_config
print('Live schema smoke OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Live schema smoke OK', result.stdout)
