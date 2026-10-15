import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from actions.video_player import video_player, _play_youtube, _begin_open


class MediaActionTests(unittest.TestCase):
    def test_local_url_and_youtube_open_with_sound(self):
        player = Mock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'clip.mp4'
            path.write_bytes(b'fixture')
            video_player({'action': 'play', 'source': str(path)}, player=player)
            self.assertFalse(player.show_video.call_args.kwargs['muted'])
        video_player({'action': 'play', 'source': 'https://example.com/video.mp4'}, player=player)
        self.assertFalse(player.show_video.call_args.kwargs['muted'])
        with patch('actions.video_player._resolve_youtube', return_value=('https://example.com/video', 'https://example.com/audio', 'Test', '')):
            _play_youtube(player, 'test video', _begin_open())
        self.assertFalse(player.show_video.call_args.kwargs['muted'])
        self.assertEqual(player.show_video.call_args.kwargs['audio_source'], 'https://example.com/audio')


class DesktopMediaTests(unittest.TestCase):
    def test_merged_controls_and_separate_media_keep_microphone_active(self):
        script = '''
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication,QPushButton
from ui import JarvisUI
app=QApplication([])
ui=JarvisUI('face.png');w=ui._win
assert w._desktop_mode
assert w.centralWidget() is not w._legacy_surface
ui._bar.open_main_window()
app.processEvents()
assert w.isVisible() and not w._legacy_surface.isVisible()
assert w._quick_drawer.isVisible() and w._ctrl_drawer.isVisible()
assert 'Settings & Controls' in w.windowTitle()
labels=[button.text() for button in w.centralWidget().findChildren(QPushButton)]
assert any('WHATSAPP CONNECTION' in text for text in labels)
assert any('AUDIO DEVICES' in text for text in labels)
assert any('MORNING BRIEF' in text for text in labels)
w._set_muted(True)
with patch.object(w._video_player,'setSource'),patch.object(w._video_player,'play'),patch.object(w._video_sound,'setSource'),patch.object(w._video_sound,'play'):
    w._on_video_open('https://example.com/video.mp4','Test media',True,'https://example.com/audio')
    app.processEvents()
    assert w._media_window.isVisible() and w._video_cont.isVisible()
    assert not w._muted and not w._video_audio.isMuted() and not w._video_sound_out.isMuted()
    w._set_video_muted(True)
    assert not w._muted
    w._set_video_muted(False)
    assert not w._muted
    w.close()
    app.processEvents()
    assert w._media_window.isVisible()
    w._media_window.close()
    assert not w.video_is_playing() and not w._media_window.isVisible()
ui._bar.shutdown();w._unsubscribe_runtime();w.close()
print('Desktop media integration OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Desktop media integration OK', result.stdout)
