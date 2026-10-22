"""Zaya · Vision & Virtual Keyboard Control Center.
Created and developed by Sajan Rai for Zaya.

Integrated webcam preview, MediaPipe landmark overlay, and full virtual keyboard.
"""
from __future__ import annotations

import threading
import time
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QLabel,
    QFrame, QWidget, QSizePolicy
)
from .settings import load, HandSettings
from .virtual_keyboard import keyboard_layout


class PreviewCanvas(QWidget):
    """Paints live camera image with optional MediaPipe landmark skeleton overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pixmap: QPixmap | None = None
        self.show_landmarks = True
        self.hands = ()
        self.gesture = 'NONE'
        self.confidence = 0.0
        self.camera_state = 'OFF'
        self.camera_error = ''

    def update_frame(self, jpeg_bytes: bytes):
        if jpeg_bytes:
            pix = QPixmap()
            if pix.loadFromData(jpeg_bytes):
                self.pixmap = pix
                self.update()

    def set_telemetry(self, camera_state: str, hands: tuple, gesture: str, confidence: float, error: str = ''):
        self.camera_state = camera_state
        self.hands = hands
        self.gesture = gesture
        self.confidence = confidence
        self.camera_error = error
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#050A0D'))

        if self.camera_state != 'ACTIVE' or self.pixmap is None:
            painter.setPen(QColor('#00B8D4'))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            if self.camera_state == 'ERROR':
                painter.setPen(QColor('#ff5252'))
                msg = f"CAMERA ERROR\n{self.camera_error or 'Camera failed to start.'}"
            elif self.camera_state == 'ACTIVE':
                msg = 'Waiting for camera frame...'
            elif self.camera_state == 'STARTING':
                msg = 'Camera STARTING...'
            else:
                msg = 'Camera OFF'
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
            return

        pw, ph = self.pixmap.width(), self.pixmap.height()
        ww, wh = self.width(), self.height()
        scale = min(ww / pw, wh / ph)
        dw, dh = int(pw * scale), int(ph * scale)
        dx, dy = (ww - dw) // 2, (wh - dh) // 2

        painter.drawPixmap(dx, dy, dw, dh, self.pixmap)

        if not self.show_landmarks or not self.hands:
            return

        CONNECTIONS = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17), (0, 17)
        ]

        for hand in self.hands:
            pts = [QPointF(dx + p.x * dw, dy + p.y * dh) for p in hand.landmarks]

            # Connections (cyan)
            painter.setPen(QPen(QColor(0, 229, 255, 200), 2))
            for a, b in CONNECTIONS:
                if a < len(pts) and b < len(pts):
                    painter.drawLine(pts[a], pts[b])

            # Landmark dots (cyan/white)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 229, 255, 220)))
            for i, pt in enumerate(pts):
                if i not in (4, 8, 12, 16, 20):
                    painter.drawEllipse(pt, 3, 3)
                else:
                    painter.drawEllipse(pt, 4.5, 4.5)

            # Palm center (white/cyan)
            if hasattr(hand, 'palm_center'):
                pcx = dx + hand.palm_center.x * dw
                pcy = dy + hand.palm_center.y * dh
                painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
                painter.drawEllipse(QPointF(pcx, pcy), 5, 5)
                painter.setPen(QPen(QColor(0, 229, 255, 180), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(pcx, pcy), 9, 9)

            # Index fingertip (bright cyan glow)
            if len(pts) > 8:
                tip = pts[8]
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(0, 229, 255, 60)))
                painter.drawEllipse(tip, 16, 16)
                painter.setBrush(QBrush(QColor(0, 229, 255, 120)))
                painter.drawEllipse(tip, 10, 10)
                painter.setBrush(QBrush(QColor(0, 229, 255, 255)))
                painter.drawEllipse(tip, 5.5, 5.5)
                painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
                painter.drawEllipse(tip, 2, 2)

            # Handedness / gesture / confidence tag
            if pts:
                wrist = pts[0]
                badge = f"{hand.handedness} · {self.gesture} ({int(hand.confidence*100)}%)"
                painter.setPen(QColor('#ffffff'))
                painter.setBrush(QBrush(QColor(5, 10, 13, 210)))
                rect = QRectF(wrist.x() - 60, min(dh + dy - 24, wrist.y() + 8), 135, 20)
                painter.drawRoundedRect(rect, 4, 4)
                font = painter.font()
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, badge)


class VirtualKeyboardCanvas(QWidget):
    """Renders the full virtual keyboard layout with key highlight & armed/latched states."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMaximumHeight(340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.keys = keyboard_layout()
        self.packet = {}

    def set_packet(self, packet: dict):
        self.packet = packet or {}
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#071014'))

        state = self.packet.get('state', 'idle')
        hovered_id = self.packet.get('key') or self.packet.get('hovered')
        latched_mods = set(self.packet.get('modifiers', []))

        w = self.width()
        h = self.height()
        pad = 4
        top_offset = 6
        avail_h = h - top_offset - 8

        for key in self.keys:
            kx, ky, kw, kh = key.bounds
            rx = kx * w + pad
            ry = top_offset + ky * avail_h + pad
            rw = kw * w - pad * 2
            rh = kh * avail_h - pad * 2
            rect = QRectF(rx, ry, rw, rh)

            is_hovered = (key.id == hovered_id)
            is_latched = (key.output.lower() in latched_mods)

            if is_hovered:
                if state == 'locked':
                    bg = QColor(0, 229, 255, 180)
                    border = QColor('#ffffff')
                elif state == 'armed':
                    bg = QColor(0, 229, 255, 120)
                    border = QColor('#00E5FF')
                elif state == 'candidate':
                    bg = QColor(0, 184, 212, 70)
                    border = QColor('#00B8D4')
                else:
                    bg = QColor(0, 229, 255, 35)
                    border = QColor('#00B8D4')
                text_col = QColor('#ffffff')
                pen_width = 2.0
            elif is_latched:
                bg = QColor(0, 184, 212, 80)
                border = QColor('#00E5FF')
                text_col = QColor('#E0F7FA')
                pen_width = 1.6
            else:
                bg = QColor(7, 16, 20, 200)
                border = QColor(0, 184, 212, 90)
                text_col = QColor('#B2EBF2')
                pen_width = 1.0

            painter.setPen(QPen(border, pen_width))
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(rect, 5, 5)

            painter.setPen(text_col)
            font = painter.font()
            font.setPointSize(9 if len(key.label) > 3 else 10)
            font.setBold(is_hovered or is_latched)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, key.label)


class PreviewThread(QThread):
    """Background worker polling JPEG snapshots from the existing camera owner."""
    frame_ready = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

    def run(self):
        from .controller import hands
        target_interval = 1 / 12
        while self.running and not self.isInterruptionRequested():
            if hands.tracker.state == 'ACTIVE':
                started = time.monotonic()
                frame = hands.tracker.capture_frame(timeout=0.25)
                if frame:
                    self.frame_ready.emit(frame)
                time.sleep(max(0.01, target_interval - (time.monotonic() - started)))
            else:
                time.sleep(0.25)

    def stop(self):
        self.running = False
        self.requestInterruption()
        if self.isRunning():
            self.wait(1500)


class HandSettingsPanel(QDialog):
    """Zaya · Virtual Keyboard / Vision Control Center."""
    completed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ZAYA · VIRTUAL KEYBOARD')
        self.resize(1280, 800)
        self.setMinimumSize(900, 640)
        self.setStyleSheet("""
            QDialog {
                background-color: #071014;
                color: #E0F7FA;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #B2EBF2;
            }
            QFrame#panel {
                background-color: rgba(11, 21, 26, 0.72);
                border: 1px solid rgba(0, 184, 212, 0.45);
                border-radius: 10px;
            }
            QPushButton {
                background-color: rgba(7, 16, 20, 0.85);
                color: #B2EBF2;
                border: 1px solid rgba(0, 184, 212, 0.5);
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.12);
                border-color: #00E5FF;
                color: #E0F7FA;
            }
            QPushButton:pressed {
                background-color: rgba(0, 229, 255, 0.22);
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: rgba(7, 16, 20, 0.85);
                color: #E0F7FA;
                border: 1px solid rgba(0, 184, 212, 0.5);
                border-radius: 4px;
                padding: 3px 6px;
            }
            QCheckBox {
                color: #B2EBF2;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                background-color: rgba(7, 16, 20, 0.85);
                border: 1px solid rgba(0, 184, 212, 0.5);
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #00B8D4;
                border-color: #00E5FF;
            }
        """)

        try:
            settings = load()
        except (OSError, ValueError, TypeError):
            settings = HandSettings()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        title_label = QLabel('ZAYA · VIRTUAL KEYBOARD')
        title_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #00E5FF; letter-spacing: 2px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.lbl_status_pill = QLabel('OFF')
        self.lbl_status_pill.setStyleSheet("color: #9ca3af; font-weight: 700; padding: 4px 10px; border: 1px solid rgba(0,184,212,0.4); border-radius: 10px;")
        header_layout.addWidget(self.lbl_status_pill)

        close_btn = QPushButton('× Close')
        close_btn.setStyleSheet("background-color: rgba(255, 82, 82, 0.12); color: #ff8a80; border: 1px solid rgba(255, 82, 82, 0.5); font-weight: 700;")
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        root_layout.addLayout(header_layout)

        # Main area: camera (left, large) + telemetry (right)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(12)

        # Left: Live Preview container
        preview_container = QVBoxLayout()
        preview_container.setSpacing(6)
        self.preview = PreviewCanvas(self)
        preview_container.addWidget(self.preview, 1)

        self.cb_landmarks = QCheckBox('Show landmarks')
        self.cb_landmarks.setChecked(True)
        self.cb_landmarks.toggled.connect(self._toggle_landmarks)
        preview_container.addWidget(self.cb_landmarks)
        main_layout.addLayout(preview_container, 7)

        # Right: Telemetry & Config Card
        right_card = QFrame(self)
        right_card.setObjectName('panel')
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(6)

        telemetry_title = QLabel('SYSTEM TELEMETRY')
        telemetry_title.setStyleSheet("font-weight: 700; color: #00B8D4; font-size: 11px; letter-spacing: 1px;")
        right_layout.addWidget(telemetry_title)

        self.lbl_camera = QLabel('Camera: OFF')
        self.lbl_device = QLabel(f'Device: {settings.device}')
        self.lbl_fps = QLabel(f'FPS: {settings.fps}')
        self.lbl_hands = QLabel('Hands: 0')
        self.lbl_gesture = QLabel('Gesture: —')
        self.lbl_confidence = QLabel('Confidence: —')
        self.lbl_mode = QLabel('Mode: NAVIGATION')
        self.lbl_hovered = QLabel('Hovered: —')
        self.lbl_last = QLabel('Last sent: —')
        self.lbl_modifiers = QLabel('Modifiers: —')

        for lbl in (self.lbl_camera, self.lbl_device, self.lbl_fps, self.lbl_hands, self.lbl_gesture, self.lbl_confidence, self.lbl_mode, self.lbl_hovered, self.lbl_last, self.lbl_modifiers):
            right_layout.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(0,184,212,0.3);")
        right_layout.addWidget(sep)

        settings_title = QLabel('CAMERA CONFIG')
        settings_title.setStyleSheet("font-weight: 700; color: #00B8D4; font-size: 11px; letter-spacing: 1px;")
        right_layout.addWidget(settings_title)

        form = QFormLayout()
        form.setSpacing(6)
        self.mode = QComboBox()
        self.mode.addItems(['NAVIGATION', 'KEYBOARD', 'SPATIAL', 'SELECTION'])
        form.addRow('Interaction', self.mode)

        self.device = QSpinBox()
        self.device.setRange(0, 31)
        self.device.setValue(settings.device)
        form.addRow('Camera Device', self.device)

        self.fps = QSpinBox()
        self.fps.setRange(10, 30)
        self.fps.setValue(settings.fps)
        form.addRow('Target FPS', self.fps)

        self.mirror = QCheckBox()
        self.mirror.setChecked(settings.mirror)
        form.addRow('Mirror Movement', self.mirror)

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(.65, .95)
        self.confidence.setSingleStep(.05)
        self.confidence.setValue(settings.confidence)
        form.addRow('Tracking Confidence', self.confidence)

        self.sensitivity = QDoubleSpinBox()
        self.sensitivity.setRange(.5, 2.0)
        self.sensitivity.setValue(settings.sensitivity)
        form.addRow('Typing Sensitivity', self.sensitivity)

        right_layout.addLayout(form)
        right_layout.addStretch()
        main_layout.addWidget(right_card, 3)
        root_layout.addLayout(main_layout, 6)

        # Mode Selection Bar
        mode_bar = QHBoxLayout()
        mode_bar.setSpacing(8)
        self.mode_buttons: dict[str, QPushButton] = {}
        for m in ['NAVIGATION', 'KEYBOARD', 'SPATIAL', 'SELECTION']:
            btn = QPushButton(m)
            btn.clicked.connect(lambda _checked, mode_name=m: self.switch_mode(mode_name))
            self.mode_buttons[m] = btn
            mode_bar.addWidget(btn)
        root_layout.addLayout(mode_bar)

        # Virtual Keyboard Section (visible only in KEYBOARD mode)
        self.keyboard_canvas = VirtualKeyboardCanvas(self)
        self.keyboard_canvas.setVisible(False)
        root_layout.addWidget(self.keyboard_canvas, 3)

        # Telemetry Status Strip
        self.telemetry_strip = QLabel('Gesture: —    Keyboard: IDLE    Hovered: —    Last sent: —    Modifiers: —    Selected part: —')
        self.telemetry_strip.setStyleSheet("background-color: rgba(7,16,20,0.85); border: 1px solid rgba(0,184,212,0.4); border-radius: 6px; padding: 6px; font-family: monospace; font-size: 11px; color: #B2EBF2;")
        root_layout.addWidget(self.telemetry_strip)

        # General status message
        self.status = QLabel('Camera off until enabled. Safe generic default is NAVIGATION.')
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #9ca3af; font-size: 11px;")
        root_layout.addWidget(self.status)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.start_button = QPushButton('Start')
        self.start_button.setStyleSheet("background-color: rgba(0, 229, 255, 0.15); border-color: #00E5FF; font-weight: 700; color: #E0F7FA;")
        self.start_button.clicked.connect(self.start)
        actions_row.addWidget(self.start_button)

        pause_btn = QPushButton('Pause')
        pause_btn.clicked.connect(lambda: self.run({'action': 'pause'}))
        actions_row.addWidget(pause_btn)

        resume_btn = QPushButton('Resume')
        resume_btn.clicked.connect(lambda: self.run({'action': 'resume'}))
        actions_row.addWidget(resume_btn)

        stop_btn = QPushButton('Stop')
        stop_btn.setStyleSheet("background-color: rgba(255, 82, 82, 0.12); border-color: rgba(255,82,82,0.5); color: #ff8a80;")
        stop_btn.clicked.connect(lambda: self.run({'action': 'stop'}))
        actions_row.addWidget(stop_btn)

        workspace_btn = QPushButton('Open 3D Workspace')
        workspace_btn.clicked.connect(self.open_workspace)
        actions_row.addWidget(workspace_btn)

        root_layout.addLayout(actions_row)

        self.completed.connect(self.finish)

        # Sync mode combobox changes
        self.mode.currentTextChanged.connect(self.switch_mode)

        # Preview background thread
        self.preview_thread = None
        self._last_camera_state = 'OFF'
        self._ensure_preview_thread()

        # Telemetry refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)

    def _ensure_preview_thread(self):
        if self.preview_thread is not None and self.preview_thread.isRunning():
            return
        thread = PreviewThread(self)
        thread.frame_ready.connect(self.preview.update_frame)
        self.preview_thread = thread
        thread.start()

    def _stop_preview_thread(self):
        thread = self.preview_thread
        self.preview_thread = None
        if thread is not None:
            thread.stop()
            thread.deleteLater()

    def showEvent(self, event):
        self._ensure_preview_thread()
        if not self.timer.isActive():
            self.timer.start(50)
        super().showEvent(event)

    def closeEvent(self, event):
        self._stop_preview_thread()
        if self.timer is not None:
            self.timer.stop()
        # Closing the fullscreen UI must revoke typing even though the camera
        # may stay warm in NAVIGATION for the next hand-control request.
        try:
            from .controller import hands
            if hands.tracker.state == 'ACTIVE':
                hands.set_mode('NAVIGATION')
        except (ImportError, RuntimeError, ValueError):
            pass
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _toggle_landmarks(self, checked: bool):
        self.preview.show_landmarks = checked
        self.preview.update()

    def set_mode_ui(self, mode_name: str):
        self.switch_mode(mode_name)

    def switch_mode(self, mode_name: str):
        if self.mode.currentText() != mode_name:
            self.mode.setCurrentText(mode_name)
        from .controller import hands
        if hands.tracker.state == 'ACTIVE':
            hands.set_mode(mode_name, sensitivity=self.sensitivity.value())
        self.keyboard_canvas.setVisible(mode_name == 'KEYBOARD')
        self._update_mode_buttons(mode_name)

    def _update_mode_buttons(self, active_mode: str):
        for name, btn in self.mode_buttons.items():
            if name == active_mode:
                btn.setStyleSheet("background-color: rgba(0, 229, 255, 0.22); color: #E0F7FA; font-weight: 700; border: 1px solid #00E5FF; border-radius: 6px; padding: 6px 12px;")
            else:
                btn.setStyleSheet("background-color: rgba(7, 16, 20, 0.85); color: #B2EBF2; border: 1px solid rgba(0, 184, 212, 0.5); border-radius: 6px; padding: 6px 12px;")

    def start(self):
        self.run({
            'action': 'start',
            'mode': self.mode.currentText(),
            'device': self.device.value(),
            'fps': self.fps.value(),
            'mirror': self.mirror.isChecked(),
            'confidence': self.confidence.value(),
            'sensitivity': self.sensitivity.value()
        })

    def run(self, parameters: dict):
        self.start_button.setEnabled(False)
        def work():
            from core.execution_policy import with_trust, TRUST_LOCAL_OWNER
            from actions.hand_controls import hand_controls
            with with_trust(TRUST_LOCAL_OWNER):
                result = hand_controls(parameters)
            self.completed.emit(result.summary)
        threading.Thread(target=work, daemon=True, name='ZayaHandSettings').start()

    def open_workspace(self):
        def work():
            from core.execution_policy import with_trust, TRUST_LOCAL_OWNER
            from actions.spatial_workspace import spatial_workspace
            with with_trust(TRUST_LOCAL_OWNER):
                result = spatial_workspace({'action': 'open'})
            self.completed.emit(result.summary)
        threading.Thread(target=work, daemon=True, name='ZayaSpatialLaunch').start()

    def finish(self, text: str):
        self.status.setText(text)
        self.start_button.setEnabled(True)

    def refresh(self):
        from .controller import hands
        st = hands.status()
        cam = st.get('camera', 'OFF')
        cur_mode = st.get('mode', 'DISABLED')
        err = st.get('error', '')
        inj_err = st.get('injection_error', '')
        gesture = st.get('gesture', 'NONE')
        confidence = 0.0

        hands_list = getattr(hands, 'latest_hands', ())
        if hands_list:
            confidence = hands_list[0].confidence

        color = '#4ade80' if cam == 'ACTIVE' else ('#f59e0b' if cam in ('STARTING', 'PAUSED') else ('#ef4444' if cam == 'ERROR' else '#9ca3af'))
        self.lbl_camera.setText(f"Camera: {cam}")
        self.lbl_camera.setStyleSheet(f"font-weight: bold; color: {color};")
        self.lbl_device.setText(f"Device: {self.device.value()}")
        self.lbl_fps.setText(f"FPS: {self.fps.value()}")
        self.lbl_hands.setText(f"Hands: {len(hands_list)}")
        self.lbl_gesture.setText(f"Gesture: {gesture}")
        self.lbl_confidence.setText(f"Confidence: {confidence:.0%}" if hands_list else "Confidence: —")
        self.lbl_mode.setText(f"Mode: {cur_mode}")
        self.lbl_hovered.setText(f"Hovered: {st.get('hovered') or '—'}")
        self.lbl_last.setText(f"Last sent: {getattr(hands, 'latest_packet', {}).get('sent') or '—'}")
        self.lbl_modifiers.setText(f"Modifiers: {' + '.join(st.get('modifiers', [])) or '—'}")

        self.preview.set_telemetry(cam, hands_list, gesture, confidence, err)

        packet = getattr(hands, 'latest_packet', {})
        self.keyboard_canvas.set_packet(packet)

        hovered = packet.get('hovered') or st.get('hovered') or '—'
        last_sent = packet.get('sent') or '—'
        mods = ' + '.join(st.get('modifiers', [])) or '—'
        selected_part = packet.get('selected_part') or st.get('selected_part') or '—'
        kb_state = packet.get('state') or st.get('keyboard') or 'idle'

        strip = f"Gesture: {gesture}    Keyboard: {kb_state.upper()}    Hovered: {hovered}    Last sent: {last_sent}    Modifiers: {mods}    Selected part: {selected_part}"
        if inj_err:
            strip += f"    [Error: {inj_err}]"
        self.telemetry_strip.setText(strip)

        # A stop/error after a live session must revoke the keyboard view; a
        # manual mode selection while the camera is simply off may stay open.
        if cam in ('OFF', 'ERROR') and self._last_camera_state in ('ACTIVE', 'STARTING', 'PAUSED'):
            if self.mode.currentText() != 'NAVIGATION':
                self.mode.blockSignals(True)
                self.mode.setCurrentText('NAVIGATION')
                self.mode.blockSignals(False)
        self._last_camera_state = cam

        effective_mode = cur_mode if cur_mode != 'DISABLED' else self.mode.currentText()
        self._update_mode_buttons(effective_mode)
        self.keyboard_canvas.setVisible(effective_mode == 'KEYBOARD')

        if cam == 'ACTIVE':
            self.lbl_status_pill.setText('ACTIVE ●')
            self.lbl_status_pill.setStyleSheet("color: #4ade80; font-weight: 700; padding: 4px 10px; border: 1px solid #4ade80; border-radius: 10px;")
            self.status.setText(f"Camera ACTIVE · Mode {cur_mode}")
            self.status.setStyleSheet("color: #9ca3af; font-size: 11px;")
        elif cam == 'ERROR':
            self.lbl_status_pill.setText('ERROR')
            self.lbl_status_pill.setStyleSheet("color: #ef4444; font-weight: 700; padding: 4px 10px; border: 1px solid #ef4444; border-radius: 10px;")
            self.status.setText(f"CAMERA ERROR · {err}")
            self.status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 700;")
        elif cam == 'STARTING':
            self.lbl_status_pill.setText('STARTING')
            self.lbl_status_pill.setStyleSheet("color: #f59e0b; font-weight: 700; padding: 4px 10px; border: 1px solid #f59e0b; border-radius: 10px;")
            self.status.setText("Camera STARTING...")
            self.status.setStyleSheet("color: #f59e0b; font-size: 11px;")
        else:
            self.lbl_status_pill.setText('OFF')
            self.lbl_status_pill.setStyleSheet("color: #9ca3af; font-weight: 700; padding: 4px 10px; border: 1px solid rgba(0,184,212,0.4); border-radius: 10px;")
            self.status.setText("Camera off until enabled. Safe generic default is NAVIGATION.")
            self.status.setStyleSheet("color: #9ca3af; font-size: 11px;")


VisionControlCenter = HandSettingsPanel
