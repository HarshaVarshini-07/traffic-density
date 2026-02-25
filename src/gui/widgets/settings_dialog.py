from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QDialogButtonBox, QCheckBox, QGroupBox)
import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "camera_source": "0",
    "model_path": "yolov8n.pt",
    "one_way_lanes": [False, False, False, False], # Lanes 1-4
    "yellow_black_strip_lane": 0, # 0 for None, 1-4 for specific lane
    "confidence_threshold": 0.3
}

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Configuration")
        self.resize(400, 300)
        self.config = {}
        self.load_config()
        self.setup_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Camera Source
        h_cam = QHBoxLayout()
        h_cam.addWidget(QLabel("Camera Source (ID or File):"))
        self.edit_cam = QLineEdit(str(self.config.get("camera_source", "0")))
        h_cam.addWidget(self.edit_cam)
        layout.addLayout(h_cam)

        # Model Path
        h_model = QHBoxLayout()
        h_model.addWidget(QLabel("YOLO Model Path:"))
        self.edit_model = QLineEdit(self.config.get("model_path", "yolov8n.pt"))
        h_model.addWidget(self.edit_model)
        layout.addLayout(h_model)

        # Confidence Threshold
        h_conf = QHBoxLayout()
        h_conf.addWidget(QLabel("Confidence Threshold (0.1 - 1.0):"))
        self.edit_conf = QLineEdit(str(self.config.get("confidence_threshold", 0.3)))
        h_conf.addWidget(self.edit_conf)
        layout.addLayout(h_conf)

        # Lane Configuration
        group_lanes = QGroupBox("Lane Configuration")
        v_lanes = QVBoxLayout()
        
        self.chk_one_way = []
        one_way_data = self.config.get("one_way_lanes", [False]*4)
        
        for i in range(4):
            chk = QCheckBox(f"Lane {i+1} is One-Way")
            chk.setChecked(one_way_data[i] if i < len(one_way_data) else False)
            v_lanes.addWidget(chk)
            self.chk_one_way.append(chk)
            
        group_lanes.setLayout(v_lanes)
        layout.addWidget(group_lanes)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept_settings(self):
        self.config["camera_source"] = self.edit_cam.text()
        self.config["model_path"] = self.edit_model.text()
        try:
            val = float(self.edit_conf.text())
            self.config["confidence_threshold"] = max(0.01, min(1.0, val))
        except ValueError:
            self.config["confidence_threshold"] = 0.3
            
        self.config["one_way_lanes"] = [chk.isChecked() for chk in self.chk_one_way]
        self.save_config()
        self.accept()
