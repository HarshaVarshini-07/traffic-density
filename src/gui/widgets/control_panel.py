from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal

class ControlPanel(QWidget):
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        
        self.btn_start = QPushButton("START SYSTEM")
        self.btn_start.setObjectName("ActionBtn")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self.btn_start, stretch=2)
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_stop.setEnabled(False) 
        layout.addWidget(self.btn_stop, stretch=1)
        
        self.btn_settings = QPushButton("CONFIG")
        self.btn_settings.setMinimumHeight(40)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.btn_settings, stretch=1)

    def set_running_state(self, is_running):
        self.btn_start.setEnabled(not is_running)
        self.btn_settings.setEnabled(not is_running) # Disable settings while running
        self.btn_stop.setEnabled(is_running)
        
        if is_running:
            self.btn_start.setStyleSheet("background-color: #2D2D2D; color: #888;")
        else:
            self.btn_start.setStyleSheet("") 
            self.btn_stop.setStyleSheet("background-color: #2D2D2D; color: #888;")
