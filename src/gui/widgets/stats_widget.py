from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QProgressBar, QSizePolicy
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class StatCard(QFrame):
    def __init__(self, title, initial_value="0"):
        super().__init__()
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("StatLabel")
        layout.addWidget(self.lbl_title)
        
        self.lbl_value = QLabel(initial_value)
        self.lbl_value.setObjectName("StatValue")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_value)

    def set_value(self, value):
        self.lbl_value.setText(str(value))

class LaneStatRow(QWidget):
    def __init__(self, lane_id):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        self.lbl_name = QLabel(f"Lane {lane_id}")
        self.lbl_name.setFixedWidth(60)
        self.lbl_name.setStyleSheet("font-weight: bold; color: #BBB;")
        layout.addWidget(self.lbl_name)
        
        # Status Light
        self.light_status = QLabel("STOP")
        self.light_status.setObjectName("LightRed")
        self.light_status.setFixedWidth(60)
        self.light_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.light_status)
        
        # Density Bar
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #333;
                border-radius: 4px;
                background: #222;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #00ADB5;
                width: 1px;
            }
        """)
        self.progress.setRange(0, 20) 
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v")
        layout.addWidget(self.progress)

    def update_stat(self, density, light_state):
        self.progress.setValue(density)
        
        style_base = "color: black; border-radius: 4px; padding: 4px; font-weight: bold;"
        
        if light_state == 'G':
            self.light_status.setText("GO")
            self.light_status.setStyleSheet("background-color: #03DAC6;" + style_base)
            self.progress.setStyleSheet(self.progress.styleSheet().replace("#00ADB5", "#03DAC6").replace("#FBC02D", "#03DAC6").replace("#CF6679", "#03DAC6"))
        elif light_state == 'Y':
            self.light_status.setText("WAIT")
            self.light_status.setStyleSheet("background-color: #FBC02D;" + style_base)
            self.progress.setStyleSheet(self.progress.styleSheet().replace("#00ADB5", "#FBC02D").replace("#03DAC6", "#FBC02D").replace("#CF6679", "#FBC02D"))
        else:
            self.light_status.setText("STOP")
            self.light_status.setStyleSheet("background-color: #CF6679; color: white; border-radius: 4px; padding: 4px; font-weight: bold;")
            self.progress.setStyleSheet(self.progress.styleSheet().replace("#00ADB5", "#CF6679").replace("#03DAC6", "#CF6679").replace("#FBC02D", "#CF6679"))

class TrafficGraph(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.figure = Figure(figsize=(4, 3), dpi=100, facecolor='#1E1E1E')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.canvas)
        
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#1E1E1E')
        self.ax.tick_params(colors='#AAAAAA')
        self.ax.spines['bottom'].set_color('#333333')
        self.ax.spines['top'].set_color('#333333') 
        self.ax.spines['left'].set_color('#333333')
        self.ax.spines['right'].set_color('#333333')
        
        self.max_points = 50
        self.data = [0] * self.max_points
        self.line, = self.ax.plot(self.data, color='#00ADB5', linewidth=2)
        self.ax.set_ylim(0, 20)
        self.ax.set_title("Total Traffic Volume", color='#E0E0E0', fontsize=10)
        
        self.figure.tight_layout()

    def update_graph(self, total_count):
        self.data.append(total_count)
        if len(self.data) > self.max_points:
            self.data.pop(0)
            
        self.line.set_ydata(self.data)
        
        # Dynamic Y-axis
        max_val = max(self.data)
        if max_val > 18:
            self.ax.set_ylim(0, max_val + 5)
        else:
            self.ax.set_ylim(0, 20)
            
        self.canvas.draw()

class StatsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)
        self.layout.setSpacing(10)
        
        # Header
        header = QLabel("Real-time Analytics")
        header.setObjectName("Header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(header)
        
        # Model Info Row
        model_frame = QFrame()
        model_layout = QHBoxLayout(model_frame)
        model_layout.setContentsMargins(0,0,0,0)
        
        self.stat_model = StatCard("Model", "Loading...")
        self.stat_device = StatCard("Device", "—")
        
        model_layout.addWidget(self.stat_model)
        model_layout.addWidget(self.stat_device)
        
        self.layout.addWidget(model_frame)
        
        # System Stats Grid
        grid_frame = QFrame()
        grid_layout = QHBoxLayout(grid_frame)
        grid_layout.setContentsMargins(0,0,0,0)
        
        self.stat_fps = StatCard("FPS", "0.0")
        self.stat_total = StatCard("Total Traffic", "0")
        
        grid_layout.addWidget(self.stat_fps)
        grid_layout.addWidget(self.stat_total)
        
        self.layout.addWidget(grid_frame)
        
        # Graph
        self.graph = TrafficGraph()
        self.layout.addWidget(self.graph, stretch=3)
        
        # Lane Stats Container
        lane_frame = QFrame()
        lane_frame.setObjectName("Panel")
        lane_layout = QVBoxLayout(lane_frame)
        
        self.lane_rows = []
        for i in range(1, 5):
            row = LaneStatRow(i)
            lane_layout.addWidget(row)
            self.lane_rows.append(row)
            
        self.layout.addWidget(lane_frame, stretch=2)
        
        self.layout.addStretch()

    def update_stats(self, densities, light_states, fps=0.0):
        total = sum(densities)
        self.stat_total.set_value(total)
        self.stat_fps.set_value(f"{fps:.1f}")
        
        for i, row in enumerate(self.lane_rows):
            if i < len(densities):
                row.update_stat(densities[i], light_states[i])
                
        self.graph.update_graph(total)

    def update_model_info(self, info: dict):
        """Update model status display."""
        self.stat_model.set_value(info.get("model_type", "Unknown"))
        device = info.get("device", "CPU")
        self.stat_device.set_value(device)
        # Color the device card based on GPU/CPU
        if device == "CUDA":
            self.stat_device.lbl_value.setStyleSheet("color: #03DAC6; font-size: 18px; font-weight: bold;")
        else:
            self.stat_device.lbl_value.setStyleSheet("color: #FBC02D; font-size: 18px; font-weight: bold;")
