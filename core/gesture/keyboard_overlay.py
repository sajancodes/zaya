"""GUI-thread-only passive keyboard view; output logic lives elsewhere."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QFrame
from .virtual_keyboard import keyboard_layout


class PassiveOverlay(QFrame):
    def __init__(self):
        super().__init__(None,Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                         Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle('Zaya hand keyboard')
        self.resize(900,300)
        self.packet = {}

    def apply(self, packet):
        self.packet = packet
        if not packet.get('visible',True):
            self.hide()
            return
        if not self.isVisible():
            screen = self.screen().availableGeometry()
            self.move(screen.center().x()-self.width()//2,screen.bottom()-self.height()-20)
            self.show()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(),QColor('#201923'))
        painter.setPen(QColor('#f6c9dc'))
        state = self.packet.get('state','idle')
        if self.packet.get('mode') != 'virtual_keyboard':
            painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,str(self.packet.get('content',''))[:500])
            return
        caption = 'Zaya · '+state+' · '+(' + '.join(self.packet.get('modifiers',[])))
        if self.packet.get('sent'):
            caption += ' · sent '+self.packet['sent']
        if self.packet.get('error'):
            caption += ' · '+self.packet['error']
        painter.drawText(12,23,caption)
        for key in keyboard_layout():
            x,y,w,h=key.bounds
            rect=QRectF(x*self.width()+3,35+y*(self.height()-38),w*self.width()-6,h*(self.height()-38)-4)
            selected=self.packet.get('key')==key.id
            painter.fillRect(rect,QColor('#7b4160' if selected and state=='armed' else '#4b3242' if selected else '#302735'))
            painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,key.label)
