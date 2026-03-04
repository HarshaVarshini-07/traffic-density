from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal

class ControlPanel(QWidget):
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    lock_clicked = pyqtSignal()
    unlock_clicked = pyqtSignal()
    recalibrate_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 5)
        main_layout.setSpacing(6)
        
        # Row 1: Start / Stop / Config
        row1 = QHBoxLayout()
        
        self.btn_start = QPushButton("START SYSTEM")
        self.btn_start.setObjectName("ActionBtn")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.start_clicked.emit)
        row1.addWidget(self.btn_start, stretch=2)
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_stop.setEnabled(False)
        row1.addWidget(self.btn_stop, stretch=1)
        
        self.btn_settings = QPushButton("CONFIG")
        self.btn_settings.setMinimumHeight(40)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        row1.addWidget(self.btn_settings, stretch=1)
        
        main_layout.addLayout(row1)
        
        # Row 2: Lock / Unlock / Recalibrate
        row2 = QHBoxLayout()
        
        self.btn_lock = QPushButton("🔒 LOCK")
        self.btn_lock.setMinimumHeight(34)
        self.btn_lock.setStyleSheet("background-color: #1B5E20; color: white; border-radius: 4px; font-weight: bold;")
        self.btn_lock.clicked.connect(self.lock_clicked.emit)
        self.btn_lock.setEnabled(False)
        row2.addWidget(self.btn_lock)
        
        self.btn_unlock = QPushButton("🔓 UNLOCK")
        self.btn_unlock.setMinimumHeight(34)
        self.btn_unlock.setStyleSheet("background-color: #E65100; color: white; border-radius: 4px; font-weight: bold;")
        self.btn_unlock.clicked.connect(self.unlock_clicked.emit)
        self.btn_unlock.setEnabled(False)
        row2.addWidget(self.btn_unlock)
        
        self.btn_recalibrate = QPushButton("🔄 RECALIBRATE")
        self.btn_recalibrate.setMinimumHeight(34)
        self.btn_recalibrate.setStyleSheet("background-color: #0D47A1; color: white; border-radius: 4px; font-weight: bold;")
        self.btn_recalibrate.clicked.connect(self.recalibrate_clicked.emit)
        self.btn_recalibrate.setEnabled(False)
        row2.addWidget(self.btn_recalibrate)
        
        main_layout.addLayout(row2)

    def set_running_state(self, is_running):
        self.btn_start.setEnabled(not is_running)
        self.btn_settings.setEnabled(not is_running)
        self.btn_stop.setEnabled(is_running)
        
        # Enable calibration controls when running
        self.btn_lock.setEnabled(is_running)
        self.btn_unlock.setEnabled(is_running)
        self.btn_recalibrate.setEnabled(is_running)
        
        if is_running:
            self.btn_start.setStyleSheet("background-color: #2D2D2D; color: #888;")
        else:
            self.btn_start.setStyleSheet("")
            self.btn_stop.setStyleSheet("background-color: #2D2D2D; color: #888;")
            self.btn_lock.setEnabled(False)
            self.btn_unlock.setEnabled(False)
            self.btn_recalibrate.setEnabled(False)
