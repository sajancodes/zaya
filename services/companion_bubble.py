"""A small cloud-shaped, non-interactive caption above the companion."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget


def shorten(text, limit=140):
    text = ' '.join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:max(1, limit - 8)].rstrip() + '........'


class CompanionBubble(QWidget):
    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                         Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text = ''
        self.full_text = ''
        self.wrap_flags = Qt.TextFlag.TextWordWrap
        self.setFont(QFont('Segoe UI', 10))

    def set_text(self, text, limit=140, max_width=300):
        self.full_text = str(text)
        self.text = shorten(text, limit)
        metrics = QFontMetrics(self.font())
        width = min(max_width, max(140, metrics.horizontalAdvance(self.text) + 42))
        self.wrap_flags = Qt.TextFlag.TextWordWrap
        if any(metrics.horizontalAdvance(word) > width - 42 for word in self.text.split()):
            self.wrap_flags = Qt.TextFlag.TextWrapAnywhere
        bounds = metrics.boundingRect(0, 0, width - 42, 2000, self.wrap_flags, self.text)
        self.resize(width, max(88, bounds.height() + 66))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cloud = QPainterPath()
        cloud.addRoundedRect(QRectF(8, 10, w - 16, h - 42), 24, 24)
        for rect in [QRectF(w * .16, 3, 46, 30), QRectF(w * .44, 2, 54, 32),
                     QRectF(2, 24, 34, 34), QRectF(w - 37, 24, 34, 34)]:
            bump = QPainterPath()
            bump.addEllipse(rect)
            cloud = cloud.united(bump)
        p.setPen(QColor('#8398b0'))
        p.setBrush(QColor('#fffaf1'))
        p.drawPath(cloud)
        p.drawEllipse(QRectF(w * .73, h - 30, 13, 13))
        p.drawEllipse(QRectF(w * .78, h - 10, 6, 6))
        p.setPen(QColor('#233448'))
        p.setFont(self.font())
        p.drawText(self.rect().adjusted(21, 18, -21, -39), self.wrap_flags | Qt.AlignmentFlag.AlignCenter, self.text)
