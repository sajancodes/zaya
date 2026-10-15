"""Small desktop windows for controls and assistant-created displays."""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout


class DisplayWindow(QDialog):
    closed = pyqtSignal()

    def __init__(self, title, widget, parent, fit=None):
        super().__init__(None, Qt.WindowType.Window)
        parent.destroyed.connect(self.close)
        self.fit = fit
        self.setWindowTitle(title)
        self.setMinimumSize(360, 260)
        bounds = self.screen().availableGeometry()
        self.resize(min(960, bounds.width() - 60), min(620, bounds.height() - 60))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        widget.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit:
            QTimer.singleShot(0, self.fit)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
