"""Zaya desktop update dialog and settings card.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import threading
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QWidget
)
from core.version import version_string
from .desktop_updater import desktop_updater, UpdateStatus


class UpdateDialog(QDialog):
    """Clean update status and management dialog."""
    status_signal = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Zaya · Updates")
        self.resize(440, 260)
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
            QPushButton:disabled {
                background-color: #1d1723;
                color: #705e6b;
                border-color: #2d2334;
            }
            QProgressBar {
                border: 1px solid #45344f;
                border-radius: 4px;
                text-align: center;
                background-color: #221927;
                color: #f6c9dc;
            }
            QProgressBar::chunk {
                background-color: #7b4160;
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Title & current version
        title = QLabel("ZAYA SYSTEM UPDATES")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f6c9dc; letter-spacing: 1px;")
        layout.addWidget(title)

        self.current_label = QLabel(f"Installed: {version_string()}")
        self.current_label.setStyleSheet("color: #a894a4; font-size: 11px;")
        layout.addWidget(self.current_label)

        # Card container
        card = QFrame(self)
        card.setStyleSheet("background-color: #221a29; border: 1px solid #3b2d45; border-radius: 6px; padding: 10px;")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        self.status_label = QLabel("Ready to check for updates.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        card_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        card_layout.addWidget(self.progress_bar)

        layout.addWidget(card)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_check = QPushButton("Check for updates")
        self.btn_check.clicked.connect(self.trigger_check)
        btn_row.addWidget(self.btn_check)

        self.btn_download = QPushButton("Download update")
        self.btn_download.setVisible(False)
        self.btn_download.setStyleSheet("background-color: #4b263b; border-color: #8b3c66; font-weight: bold;")
        self.btn_download.clicked.connect(self.trigger_download)
        btn_row.addWidget(self.btn_download)

        self.btn_restart = QPushButton("Restart and update")
        self.btn_restart.setVisible(False)
        self.btn_restart.setStyleSheet("background-color: #7b4160; color: #ffffff; font-weight: bold; border-color: #c9659a;")
        self.btn_restart.clicked.connect(self.trigger_restart)
        btn_row.addWidget(self.btn_restart)

        layout.addLayout(btn_row)

        self.status_signal.connect(self._on_status_update)
        desktop_updater.add_listener(self._on_updater_event)

        # Sync with current updater status
        self._sync_ui()

    def _on_updater_event(self, status: UpdateStatus, message: str):
        self.status_signal.emit(status.value, message)

    def _on_status_update(self, status_str: str, message: str):
        self._sync_ui()

    def _sync_ui(self):
        st = desktop_updater.status
        msg = desktop_updater.error_message or (
            f"Version {desktop_updater.available_manifest.version} is available."
            if desktop_updater.available_manifest and st == UpdateStatus.AVAILABLE
            else "Checking for updates..." if st == UpdateStatus.CHECKING
            else f"Zaya is up to date." if st == UpdateStatus.UP_TO_DATE
            else "Downloading update..." if st == UpdateStatus.DOWNLOADING
            else "Update is ready to install." if st == UpdateStatus.READY
            else "Ready to check for updates."
        )

        self.status_label.setText(msg)
        self.btn_check.setEnabled(st not in (UpdateStatus.CHECKING, UpdateStatus.DOWNLOADING))

        if st == UpdateStatus.DOWNLOADING:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(desktop_updater.download_progress)
            self.btn_download.setVisible(False)
            self.btn_restart.setVisible(False)
        else:
            self.progress_bar.setVisible(False)

        if st == UpdateStatus.AVAILABLE:
            self.btn_download.setVisible(True)
            self.btn_download.setEnabled(True)
            self.btn_restart.setVisible(False)
        elif st == UpdateStatus.READY:
            self.btn_download.setVisible(False)
            self.btn_restart.setVisible(True)
        else:
            self.btn_download.setVisible(False)
            self.btn_restart.setVisible(False)

    def trigger_check(self):
        self.btn_check.setEnabled(False)
        self.status_label.setText("Checking for updates...")
        def work():
            desktop_updater.check(force=True)
        threading.Thread(target=work, daemon=True, name="ZayaUpdateCheck").start()

    def trigger_download(self):
        self.btn_download.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        def progress(rec, total):
            pct = int((rec * 100) / total) if total else 0
            desktop_updater.download_progress = pct
            self.status_signal.emit(UpdateStatus.DOWNLOADING.value, f"Downloading: {pct}%")

        def work():
            desktop_updater.download(progress_callback=progress)
        threading.Thread(target=work, daemon=True, name="ZayaUpdateDownload").start()

    def trigger_restart(self):
        desktop_updater.apply_update(restart=True, silent=True)
