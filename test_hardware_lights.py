import sys
import os

# Ensure the root directory and libs are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(current_dir, "libs")
if current_dir not in sys.path: sys.path.insert(0, current_dir)
if libs_dir not in sys.path: sys.path.insert(0, libs_dir)

# Fix DLL load issues for Windows
if sys.platform == "win32":
    torch_lib = os.path.join(libs_dir, "torch", "lib")
    if os.path.isdir(torch_lib):
        os.add_dll_directory(torch_lib)
    try:
        import torch
    except:
        pass

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QGroupBox, QGridLayout, QTextEdit)
from PyQt6.QtCore import Qt, QTimer
from src.core.esp32_bridge import ESP32Bridge

class LightButton(QPushButton):
    def __init__(self, color_char, label):
        super().__init__(label)
        self.color_char = color_char
        self.setFixedSize(60, 40)
        
        if color_char == 'R':
            self.setStyleSheet("background-color: #AA0000; color: white; font-weight: bold;")
        elif color_char == 'Y':
            self.setStyleSheet("background-color: #AAAA00; color: black; font-weight: bold;")
        elif color_char == 'G':
            self.setStyleSheet("background-color: #00AA00; color: white; font-weight: bold;")
            
    def set_active(self, active):
        if active:
            if self.color_char == 'R': self.setStyleSheet("background-color: #FF0000; color: white; border: 3px solid white; font-weight: bold;")
            elif self.color_char == 'Y': self.setStyleSheet("background-color: #FFFF00; color: black; border: 3px solid white; font-weight: bold;")
            elif self.color_char == 'G': self.setStyleSheet("background-color: #00FF00; color: white; border: 3px solid white; font-weight: bold;")
        else:
            if self.color_char == 'R': self.setStyleSheet("background-color: #550000; color: #888;")
            elif self.color_char == 'Y': self.setStyleSheet("background-color: #555500; color: #888;")
            elif self.color_char == 'G': self.setStyleSheet("background-color: #005500; color: #888;")

class LaneControl(QGroupBox):
    def __init__(self, lane_num, parent_app):
        super().__init__(f"Lane {lane_num}")
        self.lane_num = lane_num
        self.parent_app = parent_app
        self.current_state = 'R'
        
        layout = QHBoxLayout()
        self.btn_r = LightButton('R', 'RED')
        self.btn_y = LightButton('Y', 'YEL')
        self.btn_g = LightButton('G', 'GRN')
        
        self.btn_r.clicked.connect(lambda: self.set_state('R'))
        self.btn_y.clicked.connect(lambda: self.set_state('Y'))
        self.btn_g.clicked.connect(lambda: self.set_state('G'))
        
        layout.addWidget(self.btn_r)
        layout.addWidget(self.btn_y)
        layout.addWidget(self.btn_g)
        self.setLayout(layout)
        self.update_ui()
        
    def set_state(self, state):
        self.current_state = state
        self.update_ui()
        self.parent_app.send_current_states()
        
    def update_ui(self):
        self.btn_r.set_active(self.current_state == 'R')
        self.btn_y.set_active(self.current_state == 'Y')
        self.btn_g.set_active(self.current_state == 'G')

class HardwareTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hardware Traffic Light Tester")
        self.resize(600, 500)
        self.setStyleSheet("background-color: #222; color: white; font-family: Arial;")
        
        self.bridge = None
        self.lanes = []
        self.setup_ui()
        
    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # --- Connection Top Bar ---
        conn_group = QGroupBox("ESP32 Connection")
        conn_layout = QHBoxLayout()
        
        self.port_combo = QComboBox()
        self.refresh_ports()
        conn_layout.addWidget(QLabel("COM Port:"))
        conn_layout.addWidget(self.port_combo)
        
        self.btn_refresh = QPushButton("↻ Refresh")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        conn_layout.addWidget(self.btn_refresh)
        
        self.btn_connect = QPushButton("CONNECT")
        self.btn_connect.setStyleSheet("background-color: #0055AA; font-weight: bold; padding: 5px;")
        self.btn_connect.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.btn_connect)
        
        self.lbl_status = QLabel("DISCONNECTED")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.lbl_status)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # --- Light Controls ---
        lights_group = QGroupBox("Manual Light Control")
        lights_layout = QGridLayout()
        
        for i in range(4):
            lane = LaneControl(i + 1, self)
            self.lanes.append(lane)
            lights_layout.addWidget(lane, i // 2, i % 2)
            
        lights_group.setLayout(lights_layout)
        layout.addWidget(lights_group)
        
        # --- Macros ---
        macro_group = QGroupBox("Quick Actions")
        macro_layout = QHBoxLayout()
        
        btn_all_red = QPushButton("🚨 ALL RED 🚨")
        btn_all_red.setStyleSheet("background-color: #AA0000; font-weight: bold; padding: 10px;")
        btn_all_red.clicked.connect(self.set_all_red)
        
        btn_ping = QPushButton("📡 Send PING 📡")
        btn_ping.setStyleSheet("background-color: #0055AA; font-weight: bold; padding: 10px;")
        btn_ping.clicked.connect(self.send_ping)
        
        macro_layout.addWidget(btn_all_red)
        macro_layout.addWidget(btn_ping)
        macro_group.setLayout(macro_layout)
        layout.addWidget(macro_group)
        
        # --- Log ---
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #111; color: #0F0; font-family: monospace;")
        layout.addWidget(self.log_area)
        
    def refresh_ports(self):
        self.port_combo.clear()
        ports = ESP32Bridge.list_ports()
        for p in ports:
            self.port_combo.addItem(p['port'])
            
    def log(self, msg):
        self.log_area.append(msg)
        # Scroll to bottom
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def toggle_connection(self):
        if self.bridge and self.bridge.connected:
            self.bridge.disconnect()
            self.bridge = None
            self.btn_connect.setText("CONNECT")
            self.btn_connect.setStyleSheet("background-color: #0055AA; font-weight: bold; padding: 5px;")
            self.lbl_status.setText("DISCONNECTED")
            self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
            self.log("Disconnected from serial.")
        else:
            port = self.port_combo.currentText()
            if not port: return
            
            self.bridge = ESP32Bridge(port=port, baud=115200, enabled=True)
            self.log(f"Connecting to {port}...")
            if self.bridge.connect():
                self.btn_connect.setText("DISCONNECT")
                self.btn_connect.setStyleSheet("background-color: #AA0000; font-weight: bold; padding: 5px;")
                self.lbl_status.setText("CONNECTED")
                self.lbl_status.setStyleSheet("color: #0F0; font-weight: bold;")
                self.log("Connection successful!")
            else:
                self.log("Connection failed.")
                self.bridge = None

    def send_current_states(self):
        if not self.bridge or not self.bridge.connected:
            self.log("Cannot send: Not connected.")
            return
            
        states = [lane.current_state for lane in self.lanes]
        self.bridge.send_states(states)
        self.log(f"Sent: SIG:{','.join(states)}")
        
    def set_all_red(self):
        for lane in self.lanes:
            lane.current_state = 'R'
            lane.update_ui()
        self.send_current_states()
        
    def send_ping(self):
        if not self.bridge or not self.bridge.connected:
            self.log("Cannot ping: Not connected.")
            return
            
        self.log("Sending PING...")
        res = self.bridge.ping()
        if res:
            self.log("Received: PONG (Success!)")
        else:
            self.log("No valid PONG received.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HardwareTestApp()
    window.show()
    sys.exit(app.exec())
