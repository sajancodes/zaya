import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import wave
from tools.generate_poke_voices import generate
from core.zayabar_config import load_config


class PokeVoiceTests(unittest.TestCase):
    def test_generation_saves_pcm_once_and_reuses_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'zayabar.json'
            path.write_text(json.dumps({'poke_reactions': [{'text': 'Ouch!', 'image': 'ouch.png', 'audio': 'ouch.wav'}]}))
            synth = AsyncMock(return_value=(b'\0\0' * 2400, 'Ouch!'))
            with patch('tools.generate_poke_voices.synthesize_notice', synth):
                asyncio.run(generate(path))
                asyncio.run(generate(path))
            self.assertEqual(synth.call_count, 1)
            with wave.open(str(Path(folder) / 'ouch.wav'), 'rb') as stream:
                self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()), (1, 2, 24000))
                self.assertEqual(stream.getnframes(), 2400)

    def test_pairs_require_local_wav_and_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'zayabar.json'
            path.write_text(json.dumps({'poke_reactions': [{'text': 'Ouch!', 'audio': 'https://example.com/voice.mp3'}]}))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_preloaded_playback_selects_its_matching_image_without_ai(self):
        script = r'''
import json,tempfile,wave
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import QObject,pyqtSignal
from PyQt6.QtWidgets import QApplication,QMainWindow
from PyQt6.QtGui import QPixmap,QColor
from PyQt6.QtMultimedia import QSoundEffect
from services.zayabar import ZayaBar
from core.zayabar_config import load_config
class Window(QMainWindow):
    _log_sig=pyqtSignal(str)
    _muted=False
    def _toggle_mute(self): pass
class Sound(QObject):
    playingChanged=pyqtSignal()
    Status=QSoundEffect.Status
    def __init__(self,parent):
        super().__init__(parent);self.played=0;self.playing=False
    def setLoopCount(self,value): pass
    def setVolume(self,value): pass
    def setSource(self,value): self.source=value
    def status(self): return self.Status.Ready
    def play(self): self.played+=1;self.playing=True;self.playingChanged.emit()
    def stop(self): self.playing=False;self.playingChanged.emit()
    def isPlaying(self): return self.playing
app=QApplication([])
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder)
    for name,color in [('ouch','red'),('gentle','blue')]:
        picture=QPixmap(100,100);picture.fill(QColor(color));picture.save(str(root/(name+'.png')))
        with wave.open(str(root/(name+'.wav')),'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b'\0\0'*2400)
    config=load_config()
    config['poke_reactions']=[{'text':name,'image':name+'.png','audio':name+'.wav'} for name in ['ouch','gentle']]
    path=root/'zayabar.json';path.write_text(json.dumps(config))
    with patch('services.zayabar.QSoundEffect',Sound),patch('core.notification_voice.synthesize_notice') as synth:
        window=Window();bar=ZayaBar(window,path)
        activity=[];bar.reaction_audio_active.connect(activity.append)
        bar.play_reaction(0)
        assert bar.sounds[0].played==1 and bar.frame.toImage().pixelColor(50,50).red()==255
        bar.play_reaction(1)
        assert not bar.sounds[0].isPlaying()
        assert bar.sounds[1].played==1 and bar.frame.toImage().pixelColor(50,50).blue()==255
        window._muted=True
        bar.play_reaction(1)
        assert bar.sounds[1].played==1
        assert activity and activity[0] is True
        synth.assert_not_called()
        bar.shutdown()
print('Offline paired playback OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Offline paired playback OK', result.stdout)
