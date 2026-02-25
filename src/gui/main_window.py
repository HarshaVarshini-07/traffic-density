import sys
import cv2
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSlot, QThread
from PyQt6.QtGui import QImage, QPixmap, QFont

from src.core.processor import VideoProcessor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Traffic Management System - Professional Edition")
        self.setGeometry(100, 100, 1280, 720)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        
        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QHBoxLayout(main_widget)
        
        # Video Feed
        self.video_container = QWidget()
        self.video_layout = QVBoxLayout(self.video_container)
        self.layout.addWidget(self.video_container, stretch=2)
        
        self.video_label = QLabel("Initializing System...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("border: 2px solid #333; background-color: #000;")
        self.video_label.setMinimumSize(640, 640)
        self.video_layout.addWidget(self.video_label)
        
        # Sidebar for Controls and Stats
        self.sidebar = QFrame()
        self.sidebar.setStyleSheet("background-color: #2b2b2b; padding: 10px; border-radius: 10px;")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.layout.addWidget(self.sidebar, stretch=1)
        
        # Title
        title = QLabel("Traffic Control")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(title)
        
        # Stats Grid
        self.stats_grid = QGridLayout()
        self.lane_labels = []
        self.light_labels = []
        
        for i in range(4):
            # Lane Label
            lbl = QLabel(f"Lane {i+1}: 0")
            lbl.setFont(QFont("Arial", 12))
            self.lane_labels.append(lbl)
            self.stats_grid.addWidget(lbl, i, 0)
            
            # Light Status
            light = QLabel("RED")
            light.setAlignment(Qt.AlignmentFlag.AlignCenter)
            light.setStyleSheet("background-color: red; color: white; padding: 5px; border-radius: 5px; font-weight: bold;")
            light.setFixedSize(60, 30)
            self.light_labels.append(light)
            self.stats_grid.addWidget(light, i, 1)
            
        self.sidebar_layout.addLayout(self.stats_grid)
        
        self.sidebar_layout.addStretch()
        
        # System Status
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: #888;")
        self.sidebar_layout.addWidget(self.status_label)
        
        # Buttons
        self.btn_start = QPushButton("START SYSTEM")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_start.clicked.connect(self.start_system)
        self.sidebar_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("STOP SYSTEM")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        self.btn_stop.clicked.connect(self.stop_system)
        self.btn_stop.setEnabled(False)
        self.sidebar_layout.addWidget(self.btn_stop)
        
        # Threading references
        self.work_thread = None
        self.processor = None

    def start_system(self):
        self.status_label.setText("Status: Starting...")
        self.video_label.setText("Loading AI Models...")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        # Create Thread and Worker
        self.work_thread = QThread()
        self.processor = VideoProcessor()
        self.processor.moveToThread(self.work_thread)
        
        # Connect signals
        self.work_thread.started.connect(self.processor.start_processing)
        self.processor.processed_signal.connect(self.update_gui)
        self.processor.finished.connect(self.work_thread.quit)
        self.processor.finished.connect(self.processor.deleteLater)
        self.work_thread.finished.connect(self.work_thread.deleteLater)
        
        self.work_thread.start()

    def stop_system(self):
        self.status_label.setText("Status: Stopping...")
        if self.processor:
            self.processor.stop()
            # Wait for thread to finish is handled by signals
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.video_label.setText("System Off")

    @pyqtSlot(np.ndarray, list, list)
    def update_gui(self, frame, densities, light_states):
        self.status_label.setText("Status: Running")
        # Update Image
        try:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(qt_image).scaled(
                self.video_label.width(), self.video_label.height(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            print(f"Image Error: {e}")
            
        # Update Stats
        for i in range(4):
            self.lane_labels[i].setText(f"Lane {i+1}: {densities[i]}")
            
            state = light_states[i]
            if state == 'R':
                style = "background-color: #d32f2f; color: white; padding: 5px; border-radius: 5px; font-weight: bold;"
                text = "STOP"
            elif state == 'G':
                style = "background-color: #2e7d32; color: white; padding: 5px; border-radius: 5px; font-weight: bold;"
                text = "GO"
            else:
                style = "background-color: #fdd835; color: black; padding: 5px; border-radius: 5px; font-weight: bold;"
                text = "WAIT"
                
            self.light_labels[i].setText(text)
            self.light_labels[i].setStyleSheet(style)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
