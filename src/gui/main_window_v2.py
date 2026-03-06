import sys
import os
import time
import json
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QThread, pyqtSlot

# Adjust sys.path to ensure imports work from root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))

if project_root not in sys.path:
    sys.path.append(project_root)
    sys.path.append(os.path.join(project_root, "libs"))

from src.gui.styles import APP_STYLE
from src.gui.widgets.video_widget import VideoWidget
from src.gui.widgets.stats_widget import StatsWidget
from src.gui.widgets.control_panel import ControlPanel
from src.gui.widgets.settings_dialog import SettingsDialog
from src.core.processor import VideoProcessor

CONFIG_FILE = "config.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Traffic Management System - Professional Console")
        self.resize(1280, 800)
        self.setStyleSheet(APP_STYLE)
        
        self.work_thread = None
        self.processor = None
        self.settings_dialog = SettingsDialog(self)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # --- Left Side: Video ---
        self.video_widget = VideoWidget()
        main_layout.addWidget(self.video_widget, stretch=3)
        
        # --- Right Side: Dashboard ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stats_widget = StatsWidget()
        right_layout.addWidget(self.stats_widget, stretch=4)
        
        self.controls = ControlPanel()
        self.controls.start_clicked.connect(self.start_system)
        self.controls.stop_clicked.connect(self.stop_system)
        self.controls.settings_clicked.connect(self.open_settings)
        self.controls.lock_clicked.connect(self.lock_markers)
        self.controls.unlock_clicked.connect(self.unlock_markers)
        self.controls.recalibrate_clicked.connect(self.recalibrate)
        right_layout.addWidget(self.controls, stretch=1)
        
        main_layout.addWidget(right_panel, stretch=1)
        
        self.last_frame_time = time.time()
        self.fps_history = []

    def open_settings(self):
        self.settings_dialog.load_config() # Reload in case file changed
        if self.settings_dialog.exec():
            print("Settings saved.")

    def start_system(self):
        self.video_widget.set_placeholder("Initializing AI Models...")
        self.controls.set_running_state(True)
        
        # Load Config logic
        config = self.settings_dialog.config
        camera_source = config.get("camera_source", "0")
        conf_threshold = config.get("confidence_threshold", 0.3)
        
        if camera_source.isdigit():
            camera_source = int(camera_source)
            
        self.work_thread = QThread()
        self.processor = VideoProcessor(camera_source=camera_source, conf_threshold=conf_threshold) 
        self.processor.moveToThread(self.work_thread)
        
        self.work_thread.started.connect(self.processor.start_processing)
        self.processor.processed_signal.connect(self.update_gui)
        self.processor.model_info_signal.connect(self.stats_widget.update_model_info)
        self.processor.esp32_status_signal.connect(self.stats_widget.update_esp32_status)
        self.processor.finished.connect(self.work_thread.quit)
        self.processor.finished.connect(self.processor.deleteLater)
        self.work_thread.finished.connect(self.work_thread.deleteLater)
        
        self.work_thread.start()

    def lock_markers(self):
        if self.processor:
            self.processor.lock_markers()

    def unlock_markers(self):
        if self.processor:
            self.processor.unlock_markers()

    def recalibrate(self):
        if self.processor:
            self.processor.recalibrate()

    def stop_system(self):
        if self.processor:
            self.processor.stop()
        self.controls.set_running_state(False)
        self.video_widget.set_placeholder("System Stopped")

    @pyqtSlot(np.ndarray, list, list)
    def update_gui(self, frame, densities, light_states):
        current_time = time.time()
        dt = current_time - self.last_frame_time
        self.last_frame_time = current_time
        fps = 1.0 / dt if dt > 0 else 0
        
        self.fps_history.append(fps)
        if len(self.fps_history) > 30: self.fps_history.pop(0)
        avg_fps = sum(self.fps_history) / len(self.fps_history)
        
        self.video_widget.update_frame(frame)
        self.stats_widget.update_stats(densities, light_states, avg_fps)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
