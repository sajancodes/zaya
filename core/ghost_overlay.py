"""A real Qt quick-command window, controlled through queued GUI requests."""
from __future__ import annotations

import threading

_bridge = None


def install_ghost_overlay(command_callback, parent=None):
    """Call once on the Qt GUI thread; callback accepts owner-entered text."""
    global _bridge
    from PyQt6.QtCore import QObject, pyqtSignal as Signal, pyqtSlot as Slot, QThread, Qt
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import QApplication, QFrame, QVBoxLayout, QLabel, QLineEdit, QPushButton

    app = QApplication.instance()
    if app is None or QThread.currentThread() != app.thread():
        raise RuntimeError('Install the quick-command overlay on the application GUI thread.')
    if _bridge is not None:
        return _bridge

    class OverlayBridge(QObject):
        requested = Signal(object)

        def __init__(self):
            super().__init__(parent)
            self.window = QFrame(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
            self.window.setWindowTitle('Zaya quick command')
            self.window.resize(340, 140)
            layout = QVBoxLayout(self.window)
            layout.addWidget(QLabel('Zaya — at your service', self.window))
            self.entry = QLineEdit(self.window)
            self.entry.setPlaceholderText('What would you like me to do?')
            layout.addWidget(self.entry)
            send = QPushButton('Send', self.window)
            layout.addWidget(send)
            send.clicked.connect(self.submit)
            self.entry.returnPressed.connect(self.submit)
            self.requested.connect(self.apply)
            self.passive = None
            self.pending = None
            self.pending_lock = threading.Lock()
            app.aboutToQuit.connect(self.shutdown_optional)

        def shutdown_optional(self):
            from core.gesture.controller import hands
            from core.perception.screen_perception import perception
            hands.stop()
            perception.stop()
            # Optional renderer owns no voice/runtime state.
            from services.spatial_server import stop
            stop()

        def queue_passive(self, packet):
            with self.pending_lock:
                notify = self.pending is None
                self.pending = dict(packet)
            if notify:
                self.requested.emit({'passive_flush': True, 'done': threading.Event()})

        @Slot()
        def submit(self):
            text = self.entry.text().strip()
            if text:
                command_callback(text)
                self.entry.clear()

        @Slot(object)
        def apply(self, packet):
            try:
                if packet.get('cancelled'):
                    return
                if packet.get('passive_flush'):
                    with self.pending_lock:
                        latest, self.pending = self.pending, None
                    if latest is not None:
                        if self.passive is None:
                            from core.gesture.keyboard_overlay import PassiveOverlay
                            self.passive = PassiveOverlay()
                        self.passive.apply(latest)
                    return
                desired = packet['force_state']
                visible = not self.window.isVisible() if desired is None else desired
                if visible:
                    point = QCursor.pos()
                    screen = QApplication.screenAt(point) or QApplication.primaryScreen()
                    if screen:
                        rect = screen.availableGeometry()
                        point.setX(max(rect.left(), min(point.x(), rect.right() - self.window.width() + 1)))
                        point.setY(max(rect.top(), min(point.y(), rect.bottom() - self.window.height() + 1)))
                    self.window.move(point)
                    self.window.show()
                    self.window.raise_()
                    self.window.activateWindow()
                    self.entry.setFocus()
                else:
                    self.window.hide()
                packet['result'] = {'status': 'success', 'visible': self.window.isVisible(),
                                    'position': [self.window.x(), self.window.y()]}
            except Exception as error:
                packet['result'] = {'status': 'error', 'message': str(error), 'visible': False}
            finally:
                packet['done'].set()

    _bridge = OverlayBridge()
    return _bridge


def toggle_ghost_overlay_window(force_state=None):
    if _bridge is None:
        return {'status': 'error', 'visible': False, 'message': 'The Zaya quick-command window is not initialized.'}
    from PyQt6.QtCore import QThread
    packet = {'force_state': force_state, 'done': threading.Event()}
    if QThread.currentThread() == _bridge.thread():
        _bridge.apply(packet)
    else:
        _bridge.requested.emit(packet)
        if not packet['done'].wait(3):
            packet['cancelled'] = True
            return {'status': 'error', 'visible': False, 'message': 'The quick-command window did not acknowledge the request.'}
    return packet.get('result', {'status': 'error', 'visible': False})


def passive_overlay_available():
    return _bridge is not None


def update_passive_overlay(packet):
    if _bridge is not None:
        _bridge.queue_passive(packet)
