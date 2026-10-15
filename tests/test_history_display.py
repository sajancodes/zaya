import os
import subprocess
import sys
import unittest


class HistoryDisplayTests(unittest.TestCase):
    def test_history_is_batched_without_typing_queue_or_live_bubbles(self):
        script = '''
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QSignalSpy
from ui import JarvisUI
app=QApplication([])
ui=JarvisUI('face.png')
live=QSignalSpy(ui._win._log_sig)
history=[{'role':'user','text':'Old question '+str(i)} for i in range(80)]
history.append({'role':'model','text':'Old saved answer'})
ui.restore_history(history)
app.processEvents()
log=ui._win._log
assert 'You: Old question 0' in log.toPlainText()
assert 'Zaya: Old saved answer' in log.toPlainText()
assert not log._queue and not log._typing and not log._tmr.isActive()
assert len(live)==0
ui._bar.shutdown();ui._win._unsubscribe_runtime();ui._win.close()
print('Batch history display passed')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Batch history display passed', result.stdout)
