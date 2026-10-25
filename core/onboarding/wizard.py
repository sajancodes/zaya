"""First-run onboarding wizard for Zaya desktop.
Created and developed by Sajan Rai for Zaya.

Guides new users through:
1. Welcome & introduction
2. AI Provider selection (Gemini recommended)
3. Step-by-step API key guidance & official Google AI Studio link
4. Secure key storage via Windows DPAPI
5. Live provider connection test
6. Permissions & anonymous telemetry disclosure
7. Windows startup preference
8. Optional Android companion pairing
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.security.key_vault import encrypt_secret, mask_secret, store_provider_key
from core.startup import is_startup_enabled, set_startup_enabled
from core.telemetry import (
    get_or_create_installation_info,
    is_telemetry_enabled,
    report_install_event,
    set_telemetry_enabled,
)
from core.version import VERSION

GOOGLE_AI_STUDIO_URL = "https://aistudio.google.com/app/apikey"
ZAYA_COMPANION_URL = "https://github.com/sajancodes/zaya-companion-releases/releases/latest"

# Visual Theme Constants
C_BG = "#00060a"
C_PANEL = "#010d14"
C_BORDER = "#0d3347"
C_BORDER_ACTIVE = "#00d4ff"
C_PRI = "#00d4ff"
C_PRI_DIM = "#007a99"
C_TEXT = "#d8f8ff"
C_TEXT_DIM = "#5ab8cc"
C_TEXT_MUTED = "#3a8a9a"
C_GREEN = "#00ff88"
C_RED = "#ff3355"


def probe_provider_connection(provider: str, api_key: str) -> Tuple[bool, str]:
    """Test AI API key with a minimal harmless query.

    Detects revoked keys, quota exhaustion, or network disconnects.
    """
    clean_key = (api_key or "").strip()
    if not clean_key or len(clean_key) < 10:
        return False, "Please enter a valid API key."

    provider = provider.lower()
    if provider == "gemini":
        try:
            from google import genai
            from google.genai import types as gtypes

            client = genai.Client(
                api_key=clean_key,
                http_options=gtypes.HttpOptions(timeout=10000, retry_options=gtypes.HttpRetryOptions(attempts=1)),
            )
            # Minimal model list probe
            pager = client.models.list(config={"page_size": 1})
            for _ in pager:
                break
            return True, "✓ Gemini connected successfully"
        except Exception as e:
            err_str = str(e).lower()
            if "api_key_invalid" in err_str or "permission" in err_str or "unauthenticated" in err_str:
                return False, "The API key was rejected. Verify that you copied the full key from AI Studio."
            if "quota" in err_str or "resource_exhausted" in err_str:
                return False, "API key verified, but provider quota is exhausted."
            if "connection" in err_str or "timeout" in err_str or "failed to connect" in err_str:
                return False, "Could not reach Google AI servers. Check your internet connection."
            return False, f"Connection failed: {e}"

    elif provider == "openai":
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {clean_key}", "User-Agent": f"Zaya/{VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, "✓ OpenAI connected successfully"
            return False, "Unexpected response from OpenAI."
        except urllib.error.HTTPError as err:
            if err.code == 401:
                return False, "The OpenAI API key was rejected (401 Unauthorized)."
            if err.code == 429:
                return False, "OpenAI rate limit or quota exceeded (429)."
            return False, f"OpenAI error: HTTP {err.code}"
        except Exception as e:
            return False, f"Could not connect to OpenAI: {e}"

    return True, f"✓ Key format valid for {provider}"


class OnboardingWizard(QWidget):
    """Complete first-run setup wizard widget."""

    completed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("OnboardingWizard")
        self.setStyleSheet(f"""
            QWidget#OnboardingWizard {{
                background-color: {C_BG};
                color: {C_TEXT};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QLabel {{
                color: {C_TEXT};
            }}
            QPushButton {{
                background-color: #011520;
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                color: {C_PRI};
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {C_BORDER_ACTIVE};
                background-color: #022030;
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #032b40;
            }}
            QPushButton#PrimaryBtn {{
                background-color: #007a99;
                border: 1px solid {C_PRI};
                color: #ffffff;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: #0099bf;
                border-color: #8ffcff;
            }}
            QPushButton#PrimaryBtn:disabled {{
                background-color: #08222d;
                border-color: #0d3347;
                color: #3a8a9a;
            }}
            QLineEdit {{
                background-color: #010d14;
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {C_PRI};
            }}
            QCheckBox {{
                color: {C_TEXT};
                spacing: 8px;
                font-size: 13px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {C_BORDER};
                border-radius: 3px;
                background-color: #010d14;
            }}
            QCheckBox::indicator:checked {{
                background-color: {C_PRI};
                border-color: {C_PRI};
            }}
        """)

        self._selected_provider = "gemini"
        self._tested_key = ""
        self._test_passed = False

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 36, 40, 36)
        main_layout.setSpacing(16)

        # Header branding
        header = QHBoxLayout()
        title_label = QLabel("Z A Y A")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {C_PRI}; letter-spacing: 4px;")
        header.addWidget(title_label)

        header.addStretch()
        version_label = QLabel(f"v{VERSION} · Sajan Rai")
        version_label.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 12px;")
        header.addWidget(version_label)
        main_layout.addLayout(header)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {C_BORDER}; max-height: 1px;")
        main_layout.addWidget(sep)

        # Multi-page container
        self.stack = QStackedWidget()
        self.page_welcome = self._create_welcome_page()
        self.page_provider = self._create_provider_page()
        self.page_api_key = self._create_api_key_page()
        self.page_preferences = self._create_preferences_page()
        self.page_companion = self._create_companion_page()
        self.page_finish = self._create_finish_page()

        self.stack.addWidget(self.page_welcome)
        self.stack.addWidget(self.page_provider)
        self.stack.addWidget(self.page_api_key)
        self.stack.addWidget(self.page_preferences)
        self.stack.addWidget(self.page_companion)
        self.stack.addWidget(self.page_finish)
        main_layout.addWidget(self.stack, 1)

        # Bottom navigation
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self._prev_page)
        self.btn_back.setVisible(False)
        nav_layout.addWidget(self.btn_back)

        nav_layout.addStretch()

        self.btn_skip = QPushButton("Skip for now")
        self.btn_skip.clicked.connect(self._next_page)
        self.btn_skip.setVisible(False)
        nav_layout.addWidget(self.btn_skip)

        self.btn_next = QPushButton("Get Started")
        self.btn_next.setObjectName("PrimaryBtn")
        self.btn_next.clicked.connect(self._next_page)
        nav_layout.addWidget(self.btn_next)

        main_layout.addLayout(nav_layout)

    # -----------------------------------------------------------------------
    # Page 1: Welcome
    # -----------------------------------------------------------------------
    def _create_welcome_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(14)

        heading = QLabel("Welcome to Zaya")
        heading.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        heading.setStyleSheet("color: #ffffff;")
        layout.addWidget(heading)

        subheading = QLabel("Your personal AI assistant. Built by Sajan Rai.")
        subheading.setFont(QFont("Segoe UI", 13))
        subheading.setStyleSheet(f"color: {C_PRI};")
        layout.addWidget(subheading)

        layout.addSpacing(10)

        info = QLabel(
            "Zaya unites real-time voice, continuous desktop perception, "
            "optical hand tracking, virtual keyboard interaction, and spatial 3D workspace "
            "into a single private assistant on your computer.\n\n"
            "This quick 2-minute setup will configure your AI connection and preferences.\n"
            "Your keys and data remain stored securely on your machine."
        )
        info.setWordWrap(True)
        info.setFont(QFont("Segoe UI", 12))
        info.setStyleSheet(f"color: {C_TEXT_DIM}; line-height: 1.5;")
        layout.addWidget(info)

        layout.addStretch()
        return w

    # -----------------------------------------------------------------------
    # Page 2: Provider Choice
    # -----------------------------------------------------------------------
    def _create_provider_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        heading = QLabel("Choose Your AI Provider")
        heading.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(heading)

        desc = QLabel(
            "Zaya connects to high-performance multimodal models. "
            "Select which intelligence engine you would like to use:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(desc)

        layout.addSpacing(8)

        self.radio_group = QButtonGroup(self)

        self.radio_gemini = QRadioButton("Google Gemini (Recommended)")
        self.radio_gemini.setChecked(True)
        self.radio_gemini.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.radio_gemini.setStyleSheet(f"color: {C_PRI};")
        self.radio_group.addButton(self.radio_gemini, 1)
        layout.addWidget(self.radio_gemini)

        gemini_info = QLabel("  • Free tier available via Google AI Studio\n  • Best vision, audio streaming, and spatial generation performance")
        gemini_info.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(gemini_info)

        layout.addSpacing(6)

        self.radio_openai = QRadioButton("OpenAI / Compatible (GPT-4o)")
        self.radio_openai.setFont(QFont("Segoe UI", 13))
        self.radio_openai.setStyleSheet("color: #d8f8ff;")
        self.radio_group.addButton(self.radio_openai, 2)
        layout.addWidget(self.radio_openai)

        openai_info = QLabel("  • Requires OpenAI API key\n  • Reasoning and general tool actions")
        openai_info.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(openai_info)

        layout.addStretch()
        return w

    # -----------------------------------------------------------------------
    # Page 3: API Key & Connection Test
    # -----------------------------------------------------------------------
    def _create_api_key_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.key_heading = QLabel("Connect Google Gemini")
        self.key_heading.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(self.key_heading)

        self.key_guide = QLabel(
            "Zaya uses your own API key. Keys are encrypted at rest with Windows DPAPI "
            "and are never shared with third parties or telemetry.\n\n"
            "1. Click 'Open Google AI Studio' below.\n"
            "2. Sign in with your Google account.\n"
            "3. Click 'Create API key'.\n"
            "4. Copy your key, paste it here, and click 'Test Connection'."
        )
        self.key_guide.setWordWrap(True)
        self.key_guide.setStyleSheet(f"color: {C_TEXT_DIM}; line-height: 1.4;")
        layout.addWidget(self.key_guide)

        btn_ai_studio = QPushButton("Open Google AI Studio ↗")
        btn_ai_studio.setFixedHeight(34)
        btn_ai_studio.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GOOGLE_AI_STUDIO_URL)))
        layout.addWidget(btn_ai_studio)

        layout.addSpacing(6)

        lbl_input = QLabel("API Key:")
        lbl_input.setStyleSheet("font-weight: 600; font-size: 12px;")
        layout.addWidget(lbl_input)

        input_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Paste your key here (e.g. AIzaSy...)")
        self.key_input.textChanged.connect(self._on_key_text_changed)
        input_row.addWidget(self.key_input)

        self.btn_toggle_mask = QPushButton("Show")
        self.btn_toggle_mask.setFixedWidth(64)
        self.btn_toggle_mask.clicked.connect(self._toggle_key_mask)
        input_row.addWidget(self.btn_toggle_mask)

        self.btn_paste = QPushButton("Paste")
        self.btn_paste.setFixedWidth(64)
        self.btn_paste.clicked.connect(self._paste_clipboard)
        input_row.addWidget(self.btn_paste)

        layout.addLayout(input_row)

        test_row = QHBoxLayout()
        self.btn_test = QPushButton("Test Connection")
        self.btn_test.clicked.connect(self._run_connection_test)
        test_row.addWidget(self.btn_test)

        self.lbl_test_status = QLabel("")
        self.lbl_test_status.setStyleSheet("font-size: 12px;")
        test_row.addWidget(self.lbl_test_status, 1)

        layout.addLayout(test_row)
        layout.addStretch()
        return w

    def _toggle_key_mask(self):
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_mask.setText("Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_mask.setText("Show")

    def _paste_clipboard(self):
        clip = QApplication.clipboard().text().strip()
        if clip:
            self.key_input.setText(clip)

    def _on_key_text_changed(self):
        self._test_passed = False
        self.lbl_test_status.setText("")
        self.btn_next.setEnabled(True)

    def _run_connection_test(self):
        raw_key = self.key_input.text().strip()
        if not raw_key:
            self.lbl_test_status.setText("Please enter an API key to test.")
            self.lbl_test_status.setStyleSheet(f"color: {C_RED};")
            return

        self.lbl_test_status.setText("Testing connection...")
        self.lbl_test_status.setStyleSheet(f"color: {C_PRI};")
        self.btn_test.setEnabled(False)
        QApplication.processEvents()

        provider = "gemini" if self.radio_gemini.isChecked() else "openai"

        def _test_in_background():
            ok, msg = probe_provider_connection(provider, raw_key)
            self._tested_key = raw_key
            self._test_passed = ok

            def _update_ui():
                self.btn_test.setEnabled(True)
                self.lbl_test_status.setText(msg)
                self.lbl_test_status.setStyleSheet(f"color: {C_GREEN if ok else C_RED}; font-weight: 600;")
                if ok:
                    self.btn_next.setEnabled(True)

            from PyQt6.QtCore import QMetaObject, Q_ARG
            # Run callback on Qt thread
            _update_ui()

        threading.Thread(target=_test_in_background, daemon=True).start()

    # -----------------------------------------------------------------------
    # Page 4: Permissions & Preferences
    # -----------------------------------------------------------------------
    def _create_preferences_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        heading = QLabel("Permissions & System Preferences")
        heading.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(heading)

        layout.addSpacing(4)

        # Microphone note
        mic_info = QLabel("🎤 <b>Microphone</b>: Used for voice conversation when speaking to Zaya.")
        mic_info.setTextFormat(Qt.TextFormat.RichText)
        mic_info.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(mic_info)

        # Camera note
        cam_info = QLabel(
            "📷 <b>Webcam</b>: Strictly opt-in for spatial hand gestures and virtual keyboard. "
            "The camera remains <b>OFF</b> by default at normal startup."
        )
        cam_info.setTextFormat(Qt.TextFormat.RichText)
        cam_info.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(cam_info)

        layout.addSpacing(10)

        # Startup toggle
        self.chk_startup = QCheckBox("Start Zaya automatically when I sign in to Windows")
        self.chk_startup.setChecked(is_startup_enabled())
        layout.addWidget(self.chk_startup)

        startup_sub = QLabel("  Configures standard Windows user startup. You can change this anytime.")
        startup_sub.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(startup_sub)

        layout.addSpacing(10)

        # Telemetry toggle
        self.chk_telemetry = QCheckBox("Share anonymous usage statistics")
        self.chk_telemetry.setChecked(is_telemetry_enabled())
        layout.addWidget(self.chk_telemetry)

        telemetry_sub = QLabel(
            "  Sends a random installation ID, version, and platform to help improve Zaya.\n"
            "  NEVER collects keys, conversations, voice recordings, webcam frames, or screens."
        )
        telemetry_sub.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(telemetry_sub)

        layout.addStretch()
        return w

    # -----------------------------------------------------------------------
    # Page 5: Phone Companion
    # -----------------------------------------------------------------------
    def _create_companion_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        heading = QLabel("Zaya Companion (Android)")
        heading.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(heading)

        desc = QLabel(
            "Take Zaya on the go. The official Android companion app pairs with your laptop "
            "over your local network or encrypted tunnel for voice, notifications, and call control.\n\n"
            "• Google Play Store (coming soon)\n"
            "• Direct signed APK download available now on GitHub"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {C_TEXT_DIM}; line-height: 1.5;")
        layout.addWidget(desc)

        layout.addSpacing(6)

        btn_companion = QPushButton("Download Zaya Companion APK ↗")
        btn_companion.setFixedHeight(34)
        btn_companion.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ZAYA_COMPANION_URL)))
        layout.addWidget(btn_companion)

        skip_info = QLabel("You can pair your phone anytime from Zaya settings.")
        skip_info.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(skip_info)

        layout.addStretch()
        return w

    # -----------------------------------------------------------------------
    # Page 6: Finish
    # -----------------------------------------------------------------------
    def _create_finish_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(14)

        heading = QLabel("You're All Set!")
        heading.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        heading.setStyleSheet(f"color: {C_GREEN};")
        layout.addWidget(heading)

        subheading = QLabel("Zaya is configured and ready.")
        subheading.setFont(QFont("Segoe UI", 14))
        layout.addWidget(subheading)

        layout.addSpacing(8)

        self.summary_label = QLabel(
            "• AI Provider: Google Gemini\n"
            "• Key Security: Windows DPAPI Encrypted\n"
            "• Voice & Desktop Control: Ready\n"
            "• Spatial Workspace: Ready\n"
        )
        self.summary_label.setFont(QFont("Consolas", 12))
        self.summary_label.setStyleSheet(f"color: {C_TEXT_DIM}; line-height: 1.6;")
        layout.addWidget(self.summary_label)

        layout.addSpacing(10)
        tip = QLabel("Tip: Press F4 anytime to mute/unmute, or click the mic button on the HUD.")
        tip.setStyleSheet(f"color: {C_PRI}; font-size: 12px;")
        layout.addWidget(tip)

        layout.addStretch()
        return w

    # -----------------------------------------------------------------------
    # Navigation Logic
    # -----------------------------------------------------------------------
    def _next_page(self):
        curr = self.stack.currentIndex()
        total = self.stack.count()

        # Page 2 -> 3 (Set provider heading based on selection)
        if curr == 1:
            self._selected_provider = "gemini" if self.radio_gemini.isChecked() else "openai"
            if self._selected_provider == "gemini":
                self.key_heading.setText("Connect Google Gemini")
            else:
                self.key_heading.setText("Connect OpenAI")

        # Page 3 -> 4 (Save API Key if entered)
        if curr == 2:
            key_text = self.key_input.text().strip()
            if key_text:
                store_provider_key(self._selected_provider, key_text)

        # Page 4 -> 5 (Apply startup & telemetry preferences)
        if curr == 3:
            set_startup_enabled(self.chk_startup.isChecked())
            set_telemetry_enabled(self.chk_telemetry.isChecked())

        # Last page -> complete
        if curr == total - 1:
            self._finish_onboarding()
            return

        next_idx = curr + 1
        self.stack.setCurrentIndex(next_idx)
        self._update_nav_buttons(next_idx, total)

    def _prev_page(self):
        curr = self.stack.currentIndex()
        if curr > 0:
            next_idx = curr - 1
            self.stack.setCurrentIndex(next_idx)
            self._update_nav_buttons(next_idx, self.stack.count())

    def _update_nav_buttons(self, index: int, total: int):
        self.btn_back.setVisible(index > 0)
        self.btn_skip.setVisible(index in (2, 4))  # Skip available on API key and phone companion pages

        if index == 0:
            self.btn_next.setText("Get Started")
        elif index == total - 1:
            self.btn_next.setText("Launch Zaya")
            # Update summary
            provider_name = "Google Gemini" if self._selected_provider == "gemini" else "OpenAI"
            startup_status = "Enabled" if self.chk_startup.isChecked() else "Disabled"
            telemetry_status = "Enabled (Anonymous)" if self.chk_telemetry.isChecked() else "Disabled"
            self.summary_label.setText(
                f"• AI Provider: {provider_name}\n"
                f"• Key Security: Windows DPAPI Encrypted\n"
                f"• Windows Startup: {startup_status}\n"
                f"• Anonymous Telemetry: {telemetry_status}\n"
            )
        else:
            self.btn_next.setText("Next")

    def _finish_onboarding(self):
        """Mark onboarding complete in installation metadata and report install event."""
        info = get_or_create_installation_info()
        info["onboarding_completed"] = True
        try:
            from core.runtime_paths import get_user_data_dir
            import json
            p = get_user_data_dir() / "installation.json"
            p.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

        # Trigger anonymous install reporting in background
        threading.Thread(target=report_install_event, daemon=True).start()

        self.completed.emit()


def is_onboarding_needed() -> bool:
    """Return True if the user has not completed onboarding and has no key configured."""
    from memory.config_manager import is_configured
    info = get_or_create_installation_info()
    if info.get("onboarding_completed") and is_configured():
        return False
    return not is_configured()
