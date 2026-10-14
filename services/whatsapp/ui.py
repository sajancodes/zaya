"""Small native connection panel; pairing QR codes never enter model context."""
import threading
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout
from services.whatsapp.pairing import get_pairing
from services.whatsapp.service import get_service


class WhatsAppConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Zaya · WhatsApp connection')
        self.setMinimumSize(420, 500)
        self.manager = get_pairing()
        self.connecting = False
        layout = QVBoxLayout(self)
        self.status_label = QLabel('Preparing connection…')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumSize(340, 340)
        layout.addWidget(self.qr_label)
        instructions = QLabel('On your phone: WhatsApp → Settings → Linked devices → Link a device.\nYour linked-device session is saved locally and reused by Zaya.')
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        retry = QPushButton('Connect / refresh')
        retry.clicked.connect(self.start)
        layout.addWidget(retry)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        layout.addWidget(close)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        self.start()

    def start(self):
        def work():
            try:
                self.manager.start()
            except (ValueError, OSError, RuntimeError) as error:
                self.manager.error = str(error)
                self.manager.state = 'failed'
        threading.Thread(target=work, daemon=True).start()

    def refresh(self):
        state = self.manager.status()
        if state['paired']:
            self.qr_label.clear()
            service = get_service()
            ready = bool(service.native_bridge and service.native_bridge.ready)
            self.status_label.setText('Paired · WhatsApp connected' if ready else 'Paired · reconnecting to your saved session')
            if not ready and not self.connecting:
                self.connecting = True
                threading.Thread(target=self.connect_live, daemon=True).start()
        elif state['qr_path']:
            self.status_label.setText('Scan this QR code with WhatsApp')
            self.qr_label.setPixmap(QPixmap(state['qr_path']).scaled(340, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.status_label.setText(state['error'] or 'Preparing a real WhatsApp QR code…')

    def connect_live(self):
        try:
            service = get_service()
            service.start()
            service.connect_live()
        finally:
            self.connecting = False

    def closeEvent(self, event):
        self.timer.stop()
        if not self.manager.status()['paired']:
            self.manager.cancel()
        super().closeEvent(event)
