"""Explicit local-owner controls for the optional coding package."""
import threading
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class CodingSkillDialog(QDialog):
    completed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Zaya · Coding Skill')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Optional OpenCode coding and software setup.\nInstallation requires internet. Provider setup is separate.'))
        self.status = QLabel('Checking installed package…')
        layout.addWidget(self.status)
        self.buttons = []
        for title, action in [('Install Coding Skill', 'install'), ('Update / repair pinned version', 'install'), ('Remove managed Coding Skill', 'remove')]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, action=action: self.run(action))
            layout.addWidget(button); self.buttons.append(button)
        self.completed.connect(self.finish)
        self.run('status')

    def run(self, action):
        for button in self.buttons:
            button.setEnabled(False)
        def work():
            try:
                from core import coding_skill
                result = getattr(coding_skill, action)()
            except Exception as error:
                result = 'Error · ' + str(error)[:180]
            self.completed.emit(result)
        threading.Thread(target=work, daemon=True, name='ZayaCodingSetup').start()

    def finish(self, result):
        self.status.setText(result)
        for button in self.buttons:
            button.setEnabled(True)
