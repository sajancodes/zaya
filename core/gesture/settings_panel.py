"""Zaya · Vision & Hand Control Center.
Created and developed by Sajan Rai for Zaya.

Integrated webcam preview, MediaPipe landmark overlay, and full virtual keyboard.
"""
from __future__ import annotations

import threading
import time
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QFont
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
        self.setMinimumSize(380, 285)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pixmap: QPixmap | None = None
        self.show_landmarks = True
        self.hands = ()
        self.gesture = 'NONE'
        self.confidence = 0.0
        self.camera_state = 'OFF'

    def update_frame(self, jpeg_bytes: bytes):
        if jpeg_bytes:
            pix = QPixmap()
            if pix.loadFromData(jpeg_bytes):
                self.pixmap = pix
                self.update()

    def set_telemetry(self, camera_state: str, hands: tuple, gesture: str, confidence: float):
        self.camera_state = camera_state
        self.hands = hands
        self.gesture = gesture
        self.confidence = confidence
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#140f1a'))

        if self.camera_state != 'ACTIVE' or self.pixmap is None:
            painter.setPen(QColor('#9d88a8'))
            font = painter.font()
            font.setPointSize(11)
            painter.setFont(font)
            msg = 'Camera OFF' if self.camera_state == 'OFF' else (
                f'Camera: {self.camera_state}' if self.camera_state != 'ACTIVE' else 'Waiting for camera frame...'
            )
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
            (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),        # Index
            (0, 9), (9, 10), (10, 11), (11, 12),   # Middle
            (0, 13), (13, 14), (14, 15), (15, 16), # Ring
            (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
            (5, 9), (9, 13), (13, 17), (0, 17)     # Palm
        ]

        for hand in self.hands:
            pts = [QPointF(dx + p.x * dw, dy + p.y * dh) for p in hand.landmarks]

            # Connections
            painter.setPen(QPen(QColor(224, 130, 173, 210), 2))
            for a, b in CONNECTIONS:
                if a < len(pts) and b < len(pts):
                    painter.drawLine(pts[a], pts[b])

            # Landmark dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor('#f6c9dc')))
            for i, pt in enumerate(pts):
                if i not in (4, 8, 12, 16, 20):
                    painter.drawEllipse(pt, 3, 3)
                else:
                    painter.drawEllipse(pt, 4.5, 4.5)

            # Palm center
            if hasattr(hand, 'palm_center'):
                pcx = dx + hand.palm_center.x * dw
                pcy = dy + hand.palm_center.y * dh
                painter.setBrush(QBrush(QColor('#ffd166')))
                painter.drawEllipse(QPointF(pcx, pcy), 5, 5)

            # Highlight index fingertip (landmark 8)
            if len(pts) > 8:
                tip = pts[8]
                painter.setBrush(QBrush(QColor(255, 64, 129, 90)))
                painter.drawEllipse(tip, 11, 11)
                painter.setBrush(QBrush(QColor('#ff4081')))
                painter.drawEllipse(tip, 5.5, 5.5)
                painter.setBrush(QBrush(QColor('#ffffff')))
                painter.drawEllipse(tip, 2, 2)

            # Info tag
            if pts:
                wrist = pts[0]
                badge = f"{hand.handedness} · {self.gesture} ({int(hand.confidence*100)}%)"
                painter.setPen(QColor('#ffffff'))
                painter.setBrush(QBrush(QColor(25, 18, 30, 210)))
                rect = QRectF(wrist.x() - 55, min(dh + dy - 22, wrist.y() + 8), 125, 18)
                painter.drawRoundedRect(rect, 3, 3)
                font = painter.font()
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, badge)


class VirtualKeyboardCanvas(QWidget):
    """Renders the full virtual keyboard layout with key highlight & armed/latched states."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setMaximumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.keys = keyboard_layout()
        self.packet = {}

    def set_packet(self, packet: dict):
        self.packet = packet or {}
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#18131e'))

        state = self.packet.get('state', 'idle')
        hovered_id = self.packet.get('key') or self.packet.get('hovered')
        latched_mods = set(self.packet.get('modifiers', []))

        w = self.width()
        h = self.height()
        pad = 3
        top_offset = 4
        avail_h = h - top_offset - 6

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
                if state == 'armed':
                    bg = QColor('#993d6d')
                    border = QColor('#ff85c0')
                elif state == 'locked':
                    bg = QColor('#ba4e86')
                    border = QColor('#ffffff')
                else:
                    bg = QColor('#5e3860')
                    border = QColor('#cf7ba9')
                text_col = QColor('#ffffff')
            elif is_latched:
                bg = QColor('#6b3653')
                border = QColor('#e082ad')
                text_col = QColor('#ffe6f2')
            else:
                bg = QColor('#271f2d')
                border = QColor('#3e3047')
                text_col = QColor('#e5ccdb')

            painter.setPen(QPen(border, 1.2))
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(rect, 4, 4)

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
        while self.running:
            if hands.tracker.state == 'ACTIVE':
                frame = hands.tracker.capture_frame(timeout=0.25)
                if frame:
                    self.frame_ready.emit(frame)
                time.sleep(0.09)  # ~11 FPS
            else:
                time.sleep(0.25)

    def stop(self):
        self.running = False
        self.wait(1000)


class HandSettingsPanel(QDialog):
    """Zaya · Vision & Hand Control center."""
    completed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Zaya · Vision & Hand Control')
        self.resize(760, 680)
        self.setMinimumSize(680, 580)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1420;
                color: #f6c9dc;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #e5cbda;
            }
            QPushButton {
                background-color: #2b2131;
                color: #f6c9dc;
                border: 1px solid #4a3854;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3b2c44;
                border-color: #7b4160;
            }
            QPushButton:pressed {
                background-color: #4f365c;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #221927;
                color: #f6c9dc;
                border: 1px solid #45344f;
                border-radius: 4px;
                padding: 3px 6px;
            }
            QCheckBox {
                color: #e5cbda;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                background-color: #221927;
                border: 1px solid #523e5e;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #7b4160;
                border-color: #ba6090;
            }
        """)

        try:
            settings = load()
        except (OSError, ValueError, TypeError):
            settings = HandSettings()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # Header Title
        title_label = QLabel('ZAYA · VISION & HAND CONTROL')
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f6c9dc; letter-spacing: 1px;")
        root_layout.addWidget(title_label)

        # Top section: Preview on Left, Telemetry & Settings on Right
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        # Left: Live Preview container
        preview_container = QVBoxLayout()
        self.preview = PreviewCanvas(self)
        preview_container.addWidget(self.preview)

        # Show landmarks checkbox
        self.cb_landmarks = QCheckBox('Show landmarks')
        self.cb_landmarks.setChecked(True)
        self.cb_landmarks.toggled.connect(self._toggle_landmarks)
        preview_container.addWidget(self.cb_landmarks)
        top_layout.addLayout(preview_container, 3)

        # Right: Telemetry & Config Card
        right_card = QFrame(self)
        right_card.setStyleSheet("background-color: #221a29; border: 1px solid #3b2d45; border-radius: 6px; padding: 10px;")
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(6)

        telemetry_title = QLabel('SYSTEM TELEMETRY')
        telemetry_title.setStyleSheet("font-weight: bold; color: #ba7aa3; font-size: 11px;")
        right_layout.addWidget(telemetry_title)

        self.lbl_camera = QLabel('Camera: OFF')
        self.lbl_device = QLabel(f'Device: {settings.device}')
        self.lbl_fps = QLabel(f'FPS: {settings.fps}')
        self.lbl_hands = QLabel('Hands: 0')
        self.lbl_gesture = QLabel('Gesture: —')
        self.lbl_confidence = QLabel('Confidence: —')
        self.lbl_mode = QLabel('Mode: NAVIGATION')

        for lbl in (self.lbl_camera, self.lbl_device, self.lbl_fps, self.lbl_hands, self.lbl_gesture, self.lbl_confidence, self.lbl_mode):
            right_layout.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3b2d45;")
        right_layout.addWidget(sep)

        settings_title = QLabel('CAMERA CONFIG')
        settings_title.setStyleSheet("font-weight: bold; color: #ba7aa3; font-size: 11px;")
        right_layout.addWidget(settings_title)

        # Form controls
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
        top_layout.addWidget(right_card, 2)
        root_layout.addLayout(top_layout, 1)

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
        root_layout.addWidget(self.keyboard_canvas)

        # Telemetry Status Strip
        self.telemetry_strip = QLabel('Gesture: —    Keyboard: IDLE    Hovered: —    Last sent: —    Modifiers: —    Selected part: —')
        self.telemetry_strip.setStyleSheet("background-color: #211927; border: 1px solid #3c2e47; border-radius: 4px; padding: 6px; font-family: monospace; font-size: 11px;")
        root_layout.addWidget(self.telemetry_strip)

        # General status message
        self.status = QLabel('Camera off until enabled. Safe generic default is NAVIGATION.')
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #bfa6b8; font-size: 11px;")
        root_layout.addWidget(self.status)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.start_button = QPushButton('Start')
        self.start_button.setStyleSheet("background-color: #4b263b; border-color: #8b3c66; font-weight: bold;")
        self.start_button.clicked.connect(self.start)
        actions_row.addWidget(self.start_button)

        pause_btn = QPushButton('Pause')
        pause_btn.clicked.connect(lambda: self.run({'action': 'pause'}))
        actions_row.addWidget(pause_btn)

        resume_btn = QPushButton('Resume')
        resume_btn.clicked.connect(lambda: self.run({'action': 'resume'}))
        actions_row.addWidget(resume_btn)

        stop_btn = QPushButton('Stop')
        stop_btn.setStyleSheet("background-color: #3b1e2a; border-color: #7b2a3d; color: #ff9fb2;")
        stop_btn.clicked.connect(lambda: self.run({'action': 'stop'}))
        actions_row.addWidget(stop_btn)

        workspace_btn = QPushButton('Open 3D Workspace')
        workspace_btn.setStyleSheet("background-color: #1e2c3b; border-color: #3d5f85; color: #bde0fe;")
        workspace_btn.clicked.connect(self.open_workspace)
        actions_row.addWidget(workspace_btn)

        root_layout.addLayout(actions_row)

        self.completed.connect(self.finish)

        # Sync mode combobox changes
        self.mode.currentTextChanged.connect(self.switch_mode)

        # Preview background thread
        self.preview_thread = PreviewThread(self)
        self.preview_thread.frame_ready.connect(self.preview.update_frame)
        self.preview_thread.start()

        # Telemetry refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)

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
                btn.setStyleSheet("background-color: #7b4160; color: #ffffff; font-weight: bold; border: 1px solid #c9659a; border-radius: 4px; padding: 6px 12px;")
            else:
                btn.setStyleSheet("background-color: #2b2131; color: #e5cbda; border: 1px solid #4a3854; border-radius: 4px; padding: 6px 12px;")

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
        self.lbl_confidence.setText(f"Confidence: {confidence:.2f}" if hands_list else "Confidence: —")
        self.lbl_mode.setText(f"Mode: {cur_mode}")

        self.preview.set_telemetry(cam, hands_list, gesture, confidence)

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

        effective_mode = cur_mode if cur_mode != 'DISABLED' else self.mode.currentText()
        self._update_mode_buttons(effective_mode)
        self.keyboard_canvas.setVisible(effective_mode == 'KEYBOARD')

        if cam == 'ACTIVE':
            self.status.setText(f"Camera ACTIVE · Mode {cur_mode}")
        elif cam == 'ERROR':
            self.status.setText(f"Camera ERROR · {err}")

    def closeEvent(self, event):
        self.preview_thread.stop()
        super().closeEvent(event)


VisionControlCenter = HandSettingsPanel
