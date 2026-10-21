"""Owner-operated Qt settings; capture remains off until Start is clicked."""
import threading
from PyQt6.QtCore import pyqtSignal,QTimer
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QSpinBox,QDoubleSpinBox,QCheckBox,QPushButton,QLabel
from .settings import load,HandSettings


class HandSettingsPanel(QDialog):
    completed=pyqtSignal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Zaya · hand controls & spatial workspace');self.resize(420,390)
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        try:settings=load()
        except (OSError,ValueError,TypeError):settings=HandSettings()
        self.mode=QComboBox();self.mode.addItems(['NAVIGATION','KEYBOARD','SPATIAL','SELECTION']);form.addRow('Interaction',self.mode)
        self.device=QSpinBox();self.device.setRange(0,31);self.device.setValue(settings.device);form.addRow('Camera',self.device)
        self.fps=QSpinBox();self.fps.setRange(10,30);self.fps.setValue(settings.fps);form.addRow('Updates per second',self.fps)
        self.mirror=QCheckBox();self.mirror.setChecked(settings.mirror);form.addRow('Mirror hand movement',self.mirror)
        self.confidence=QDoubleSpinBox();self.confidence.setRange(.65,.95);self.confidence.setSingleStep(.05);self.confidence.setValue(settings.confidence);form.addRow('Tracking confidence',self.confidence)
        self.sensitivity=QDoubleSpinBox();self.sensitivity.setRange(.5,2);self.sensitivity.setValue(settings.sensitivity);form.addRow('Typing sensitivity',self.sensitivity)
        self.status=QLabel('Camera off until enabled. Select another app before hand typing.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.start_button=QPushButton('Start hand controls');layout.addWidget(self.start_button);self.start_button.clicked.connect(self.start)
        stop=QPushButton('Stop and release camera');layout.addWidget(stop);stop.clicked.connect(lambda:self.run({'action':'stop'}))
        workspace=QPushButton('Open 3D workspace');layout.addWidget(workspace);workspace.clicked.connect(self.open_workspace)
        self.completed.connect(self.finish)
        timer=QTimer(self);timer.timeout.connect(self.refresh);timer.start(1000)

    def start(self):
        self.run({'action':'start','mode':self.mode.currentText(),'device':self.device.value(),'fps':self.fps.value(),
                  'mirror':self.mirror.isChecked(),'confidence':self.confidence.value(),'sensitivity':self.sensitivity.value()})

    def run(self,parameters):
        self.start_button.setEnabled(False)
        def work():
            from core.execution_policy import with_trust,TRUST_LOCAL_OWNER
            from actions.hand_controls import hand_controls
            with with_trust(TRUST_LOCAL_OWNER):
                result=hand_controls(parameters)
            self.completed.emit(result.summary)
        threading.Thread(target=work,daemon=True,name='ZayaHandSettings').start()

    def open_workspace(self):
        def work():
            from core.execution_policy import with_trust,TRUST_LOCAL_OWNER
            from actions.spatial_workspace import spatial_workspace
            with with_trust(TRUST_LOCAL_OWNER):result=spatial_workspace({'action':'open'})
            self.completed.emit(result.summary)
        threading.Thread(target=work,daemon=True,name='ZayaSpatialLaunch').start()

    def finish(self,text):
        self.status.setText(text);self.start_button.setEnabled(True)

    def refresh(self):
        from .controller import hands
        state=hands.status()
        if state['camera'] in ('ACTIVE','ERROR'):
            self.status.setText(state['camera']+' · '+state['mode']+' · '+state['error']+' '+state['injection_error'])
