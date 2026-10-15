"""Transparent taskbar sprite; all desktop interaction stays on Qt's thread."""
import json
import random
import time
import wave
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QSize, QBuffer, QIODevice, pyqtSignal
from PyQt6.QtGui import QPixmap, QMovie, QPainter, QColor, QIcon, QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import QWidget, QApplication, QMenu, QSystemTrayIcon, QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel
from core.event_bus import bus
from core.zayabar_config import CONFIG_PATH, EMOTIONS, load_config, asset_path, local_path
from services.companion_bubble import CompanionBubble


class ZayaBar(QWidget):
    state_changed = pyqtSignal(str)
    runtime_event = pyqtSignal(dict)
    reaction_requested = pyqtSignal(str)
    reaction_audio_active = pyqtSignal(bool)
    config_reloaded = pyqtSignal()

    def __init__(self, main_window, config_path=CONFIG_PATH):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.main_window, self.config_path = main_window, Path(config_path)
        self.config = load_config(self.config_path)
        self.state_path = self.config_path.parent / 'memory' / 'zayabar_state.json'
        try:
            position = json.loads(self.state_path.read_text(encoding='utf-8')).get('horizontal_position')
            if isinstance(position, (int, float)) and 0 <= position <= 1:
                self.config['horizontal_position'] = position
        except (ValueError, OSError):
            pass
        self.mode, self.emotion, self.base_state = 'standby', 'neutral', 'LISTENING'
        self.movie, self.frame, self.loaded_asset = None, QPixmap(), None
        self.last_poke, self.poked_until, self.drag_origin = -1000.0, 0.0, None
        self.active_tasks = set()
        self.selected_reaction = None
        self.pending_reaction = None
        self.sounds = {}
        self.reaction_durations = {}
        self.error = ''
        self.state_changed.connect(self.set_state)
        self.runtime_event.connect(self.on_runtime)
        self.unsubscribe = bus.subscribe('*', self.runtime_event.emit)
        self.restore_timer = QTimer(self)
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self.refresh_mode)
        self.bubble = CompanionBubble(self)
        self.bubble_kind = None
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.bubble.hide)
        self.position_timer = QTimer(self)
        self.position_timer.timeout.connect(self.position_on_taskbar)
        self.position_timer.start(1500)
        self.position_on_taskbar()
        self.load_media()
        self.preload_reactions()
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            icon = QPixmap(40, 40)
            icon.fill(QColor('#42d5cb'))
            self.tray = QSystemTrayIcon(QIcon(icon), self)
            self.tray.setToolTip('Zaya — Settings & Controls')
            menu = QMenu()
            menu.addAction('Settings & Controls', self.open_main_window)
            menu.addAction('Character configuration…', self.open_config)
            menu.addAction('Reload zayabar.json', self.reload_config)
            menu.addAction('Mute / unmute microphone', main_window._toggle_mute)
            menu.addAction('Show companion', self.show)
            menu.addAction('Exit Zaya', QApplication.instance().quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason: self.open_main_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
            self.tray.show()
        self.setToolTip('Zaya • right-click: settings & controls • double-click: poke • drag: move')

    def open_main_window(self):
        self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def contextMenuEvent(self, event):
        self.open_main_window()
        event.accept()

    def position_on_taskbar(self):
        if self.drag_origin is not None:
            return
        screens = QApplication.screens()
        index = self.config.get('screen_index', 0)
        screen = screens[index] if isinstance(index, int) and 0 <= index < len(screens) else QApplication.primaryScreen()
        full, work = screen.geometry(), screen.availableGeometry()
        floor = full.bottom() + 1
        edge = work.bottom() + 1 if work.bottom() < full.bottom() else floor - 48
        height = int(self.config['height'])
        if self.config.get('fit_legs_to_taskbar', True):
            height = min(height, int(max(1, floor - edge - 2) / (1 - self.config['seat_fraction'])))
        height = max(32, height)
        width = max(32, int(self.config['width'] * height / self.config['height']))
        old_size = self.size()
        self.resize(width, height)
        x = full.left() + int((full.width() - width) * self.config['horizontal_position'])
        y = min(floor - height - 2, edge - int(height * self.config['seat_fraction']))
        self.move(x, max(full.top(), y))
        self.position_bubble()
        if self.movie and old_size != self.size():
            self.movie.setScaledSize(self.size())

    def set_state(self, state):
        self.base_state = state
        if state == 'SPEAKING':
            for sound in self.sounds.values():
                sound.stop()
        self.refresh_mode()
        if state != 'SPEAKING' and self.pending_reaction is not None:
            index, self.pending_reaction = self.pending_reaction, None
            self.play_reaction(index)

    def preload_reactions(self):
        for sound in self.sounds.values():
            sound.stop()
            sound.deleteLater()
        self.sounds = {}
        self.reaction_durations = {}
        self.reactions = self.config['poke_reactions'] or [
            {'text': line, 'image': self.config['assets'].get('poked', ''), 'audio': ''}
            for line in self.config['reaction_lines']]
        for index, reaction in enumerate(self.reactions):
            path = local_path(reaction.get('audio', ''), self.config_path)
            if path and path.is_file():
                try:
                    with wave.open(str(path), 'rb') as stream:
                        self.reaction_durations[index] = int(1000 * stream.getnframes() / stream.getframerate()) + 150
                except (OSError, wave.Error):
                    pass
                sound = QSoundEffect(self)
                sound.setLoopCount(1)
                sound.setVolume(1.0)
                sound.setSource(QUrl.fromLocalFile(str(path.resolve())))
                sound.playingChanged.connect(self.sound_activity)
                self.sounds[index] = sound

    def sound_activity(self):
        self.reaction_audio_active.emit(any(sound.isPlaying() for sound in self.sounds.values()))

    def play_reaction(self, index):
        reaction = self.reactions[index]
        self.selected_reaction = reaction
        duration = max(self.config['reaction_duration_ms'], self.reaction_durations.get(index, 0))
        self.poked_until = time.monotonic() + duration / 1000
        self.restore_timer.start(int(duration))
        self.refresh_mode()
        self.load_media()
        self.show_bubble(reaction['text'], 'poke')
        if self.config['poke_audio_enabled'] and self.base_state == 'SPEAKING':
            self.pending_reaction = index
            self.main_window._log_sig.emit('SYS: Poke voice queued until the current speech finishes.')
        elif self.config['poke_audio_enabled']:
            sound = self.sounds.get(index)
            if sound and sound.status() == QSoundEffect.Status.Ready:
                for previous in self.sounds.values():
                    if previous.isPlaying():
                        previous.stop()
                sound.play()
                self.reaction_requested.emit(reaction['text'])
            elif not reaction.get('audio'):
                self.reaction_requested.emit(reaction['text'])
            else:
                self.main_window._log_sig.emit('SYS: Poke audio is missing or not loaded; check the local WAV path and speaker output.')

    def on_runtime(self, event):
        if event['event'] == 'avatar.caption':
            self.show_bubble(event.get('text', ''), 'reply')
        elif event['event'] == 'avatar.reaction.playing':
            duration = min(10000, max(self.config['reaction_duration_ms'], event.get('duration_ms', 0)))
            self.poked_until = time.monotonic() + duration / 1000
            self.restore_timer.start(int(duration))
            self.refresh_mode()
        elif event['event'] == 'avatar.emotion':
            if event.get('emotion') in EMOTIONS:
                self.emotion = event['emotion']
                self.load_media()
        elif event['event'].startswith('task.'):
            task = event.get('task', {})
            task_id = task.get('task_id') or task.get('id')
            if task_id:
                if task.get('state') in {'created', 'executing', 'verifying'}:
                    self.active_tasks.add(task_id)
                else:
                    self.active_tasks.discard(task_id)
            self.refresh_mode()

    def refresh_mode(self):
        mode = ('poked' if time.monotonic() < self.poked_until else 'talking' if self.base_state == 'SPEAKING'
                else 'thinking' if self.base_state == 'THINKING' or self.active_tasks else 'standby')
        if mode != self.mode:
            self.mode = mode
            self.load_media()
            if mode == 'thinking':
                self.show_bubble('Thinking...', 'thinking')
            elif self.bubble_kind == 'thinking':
                self.bubble.hide()
                self.bubble_kind = None

    def observe_log(self, text):
        if text.startswith('Zaya:'):
            self.show_bubble(text.split(':', 1)[1].strip(), 'reply')

    def show_bubble(self, text, kind='reply'):
        if not str(text).strip() or not self.config.get('enabled', True):
            return
        self.bubble_kind = kind
        self.bubble.set_text(text, self.config['bubble_max_characters'], self.config['bubble_max_width'])
        self.position_bubble()
        self.bubble.show()
        self.bubble.raise_()
        if kind == 'thinking':
            self.bubble_timer.stop()
        else:
            self.bubble_timer.start(self.config['bubble_duration_ms'])

    def position_bubble(self):
        if not hasattr(self, 'bubble'):
            return
        screen = self.screen().availableGeometry()
        x = self.x() + self.width() // 2 - int(self.bubble.width() * .78)
        y = self.y() - self.bubble.height() + 14
        x = max(screen.left() + 4, min(x, screen.right() - self.bubble.width() - 4))
        self.bubble.move(x, max(screen.top() + 4, y))

    def load_media(self):
        path = asset_path(self.config, self.mode, self.emotion, self.config_path)
        if not path or not path.is_file():
            fallbacks = []
            if self.mode == 'talking':
                fallbacks.append(asset_path(self.config, 'talking', 'neutral', self.config_path))
            fallbacks.append(asset_path(self.config, 'standby', config_path=self.config_path))
            path = next((candidate for candidate in fallbacks if candidate and candidate.is_file()), path)
        key = (str(path), self.mode, self.emotion, self.size().width(), self.size().height())
        if key == self.loaded_asset:
            return
        self.loaded_asset = key
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        self.frame = QPixmap()
        self.error = ''
        if path and path.is_file():
            if path.suffix.lower() == '.gif':
                movie = QMovie(parent=self)
                buffer = QBuffer(movie)
                buffer.setData(path.read_bytes())
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                movie.setDevice(buffer)
                if movie.isValid():
                    self.movie = movie
                    movie.setScaledSize(QSize(self.width(), self.height()))
                    movie.frameChanged.connect(self.movie_frame)
                    movie.start()
                else:
                    self.error = 'Cannot load GIF'
            else:
                self.frame = QPixmap(str(path))
                if self.frame.isNull():
                    self.error = 'Cannot load image'
        elif path:
            self.error = 'Image path missing'
        self.update()

    def movie_frame(self, _index):
        self.frame = self.movie.currentPixmap()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.frame.isNull():
            frame = self.frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width() - frame.width()) // 2, (self.height() - frame.height()) // 2, frame)
        else:
            painter.setBrush(QColor('#193b49'))
            painter.setPen(QColor('#69e5d9'))
            painter.drawRoundedRect(self.rect().adjusted(8, 8, -8, -8), 20, 20)
            painter.drawText(self.rect().adjusted(10, 10, -10, -10), Qt.AlignmentFlag.AlignCenter,
                             'Zaya\n' + (self.error or 'Add your images\nin zayabar.json'))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            now = time.monotonic()
            if now - self.last_poke >= self.config['reaction_cooldown_seconds']:
                self.last_poke = now
                self.play_reaction(random.randrange(len(self.reactions)))
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_origin = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            x = event.globalPosition().toPoint().x() - self.drag_origin.x()
            screen = self.screen().geometry()
            self.config['horizontal_position'] = max(0, min(1, (x - screen.left()) / max(1, screen.width() - self.width())))
            self.move(x, self.y())
            self.position_bubble()

    def mouseReleaseEvent(self, _event):
        self.drag_origin = None
        self.position_on_taskbar()
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({'horizontal_position': self.config['horizontal_position']}), encoding='utf-8')
        except OSError:
            pass

    def reload_config(self):
        try:
            self.config = load_config(self.config_path)
        except (ValueError, OSError) as error:
            self.main_window._log_sig.emit(f'ERR: Character configuration: {error}')
            return False
        self.loaded_asset = None
        self.selected_reaction = None
        self.preload_reactions()
        self.position_on_taskbar()
        self.load_media()
        self.setVisible(self.config.get('enabled', True))
        self.config_reloaded.emit()
        return True

    def open_config(self):
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle('Zaya character — zayabar.json')
        dialog.resize(600, 520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Set PNG / GIF paths. Use forward slashes, for example C:/Pictures/Zaya/standby.gif.'))
        editor = QTextEdit()
        editor.setPlainText(self.config_path.read_text(encoding='utf-8-sig'))
        layout.addWidget(editor)
        status = QLabel('')
        layout.addWidget(status)
        button = QPushButton('Save and reload')
        def save():
            try:
                text = editor.toPlainText()
                json.loads(text)
                temporary = self.config_path.with_suffix('.tmp')
                temporary.write_text(text, encoding='utf-8')
                load_config(temporary)
                temporary.replace(self.config_path)
                self.reload_config()
                status.setText('Saved. Your character has been reloaded.')
            except (ValueError, OSError) as error:
                status.setText(str(error))
        button.clicked.connect(save)
        layout.addWidget(button)
        external = QPushButton('Open configuration file')
        external.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config_path))))
        layout.addWidget(external)
        dialog.show()
        self.config_dialog = dialog

    def shutdown(self):
        self.bubble_timer.stop()
        self.bubble.close()
        for sound in self.sounds.values():
            sound.stop()
        self.unsubscribe()
        self.position_timer.stop()
        self.restore_timer.stop()
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        if self.tray:
            self.tray.hide()
        self.close()
