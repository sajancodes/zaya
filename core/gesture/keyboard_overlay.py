"""Zaya Canonical Holographic Air Keyboard HUD.
Created and developed by Sajan Rai for Zaya.

Top-of-screen non-activating translucent cyan HUD overlay for global Windows typing.
Target application tracking ensures keystrokes inject into the active external application
without stealing focus or ever injecting into Zaya itself.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QFrame, QApplication

from .virtual_keyboard import keyboard_layout


class PassiveOverlay(QFrame):
    """Canonical Top-of-Screen Holographic HUD Keyboard."""

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle("Zaya Air Keyboard HUD")

        self.keys = keyboard_layout()
        self.packet = {}
        self.resize(1120, 230)

    def apply(self, packet: dict):
        self.packet = packet or {}
        if not self.packet.get("visible", True):
            self.hide()
            return

        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            target_w = min(1180, int(geom.width() * 0.85))
            target_h = min(240, int(geom.height() * 0.28))
            self.resize(target_w, target_h)
            # Dock at the top center of the active monitor
            dock_x = geom.left() + (geom.width() - self.width()) // 2
            dock_y = geom.top() + 8
            self.move(dock_x, dock_y)

        if not self.isVisible():
            self.show()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Translucent futuristic HUD panel
        hud_bg = QColor(7, 16, 20, 225)
        border_pen = QPen(QColor(0, 229, 255, 140), 1.5)
        painter.setBrush(QBrush(hud_bg))
        painter.setPen(border_pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

        # Header area
        header_h = 32
        target_info = self.packet.get("target") or {}
        target_app = target_info.get("app") or self.packet.get("target_app") or "Active Window"
        is_zaya = target_info.get("is_zaya", False) or self.packet.get("is_zaya", False)

        # Title
        painter.setPen(QColor("#00E5FF"))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(16, 21, "ZAYA · AIR KEYBOARD")

        # Target application indicator badge
        target_rect = QRectF(self.width() // 2 - 160, 6, 320, 20)
        if is_zaya:
            badge_bg = QColor(255, 82, 82, 50)
            badge_border = QColor(255, 82, 82, 180)
            badge_text = "TARGET · Zaya (Injection blocked)"
            text_color = QColor("#FF8A80")
        else:
            badge_bg = QColor(0, 184, 212, 35)
            badge_border = QColor(0, 229, 255, 90)
            badge_text = f"TARGET · {target_app}"
            text_color = QColor("#E0F7FA")

        painter.setBrush(QBrush(badge_bg))
        painter.setPen(QPen(badge_border, 1.0))
        painter.drawRoundedRect(target_rect, 4, 4)
        painter.setPen(text_color)
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(target_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Status / Modifiers / State
        state = self.packet.get("state", "idle")
        mods = self.packet.get("modifiers", [])
        status_parts = [state.upper()]
        if mods:
            status_parts.append("+".join(m.upper() for m in mods))
        if self.packet.get("sent"):
            status_parts.append(f"SENT [{self.packet['sent']}]")
        if self.packet.get("error"):
            status_parts.append(f"ERR: {self.packet['error']}")
        status_str = " · ".join(status_parts)

        painter.setPen(QColor("#B2EBF2"))
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            self.width() - 280,
            6,
            260,
            20,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            status_str,
        )

        # Keys Grid
        keys_y = header_h + 4
        keys_h = self.height() - keys_y - 8
        keys_w = self.width() - 20
        keys_x = 10
        pad = 3

        hovered_key_id = self.packet.get("key") or self.packet.get("hovered")
        latched_mods = {m.lower() for m in mods}

        for key in self.keys:
            kx, ky, kw, kh = key.bounds
            rx = keys_x + kx * keys_w + pad
            ry = keys_y + ky * keys_h + pad
            rw = kw * keys_w - pad * 2
            rh = kh * keys_h - pad * 2
            rect = QRectF(rx, ry, rw, rh)

            is_hovered = (key.id == hovered_key_id)
            is_latched = (key.output.lower() in latched_mods)

            if is_hovered:
                if state == "locked":
                    bg = QColor(0, 229, 255, 210)
                    border = QColor("#FFFFFF")
                    text_col = QColor("#050A0D")
                elif state == "armed":
                    bg = QColor(0, 229, 255, 140)
                    border = QColor("#00E5FF")
                    text_col = QColor("#FFFFFF")
                else:
                    bg = QColor(0, 184, 212, 60)
                    border = QColor("#00E5FF")
                    text_col = QColor("#FFFFFF")
                pen_w = 1.8
            elif is_latched:
                bg = QColor(0, 184, 212, 90)
                border = QColor("#00E5FF")
                text_col = QColor("#E0F7FA")
                pen_w = 1.4
            else:
                bg = QColor(7, 16, 20, 180)
                border = QColor(0, 184, 212, 80)
                text_col = QColor("#B2EBF2")
                pen_w = 1.0

            painter.setPen(QPen(border, pen_w))
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(rect, 4, 4)

            painter.setPen(text_col)
            font.setPointSize(9 if len(key.label) > 3 else 10)
            font.setBold(is_hovered or is_latched)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, key.label)

        # Virtual Aim Cursor Indicator (if cursor is hovering keyboard)
        cursor_rel = self.packet.get("cursor_rel")  # (norm_x, norm_y) within keyboard bounds
        if cursor_rel:
            cx = keys_x + cursor_rel[0] * keys_w
            cy = keys_y + cursor_rel[1] * keys_h
            pt = QPointF(cx, cy)
            painter.setPen(Qt.PenStyle.NoPen)
            # Outer cyan glow halo
            painter.setBrush(QBrush(QColor(0, 229, 255, 60)))
            painter.drawEllipse(pt, 14, 14)
            painter.setBrush(QBrush(QColor(0, 229, 255, 150)))
            painter.drawEllipse(pt, 7, 7)
            # Center bright dot
            painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
            painter.drawEllipse(pt, 2.5, 2.5)


# Alias for backward compatibility
AirKeyboardOverlay = PassiveOverlay
