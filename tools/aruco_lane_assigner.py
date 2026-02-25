"""
Smart Traffic - ArUco Lane Assignment Tool
============================================
A GUI tool to detect ArUco markers from the camera and assign each marker
to a lane number (1-4) for emergency vehicle prioritization.

Usage:
    python tools/aruco_lane_assigner.py
"""
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'libs'))
sys.path.append(PROJECT_ROOT)

import cv2
import json
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor

CONFIG_FILE = os.path.join(PROJECT_ROOT, 'config.json')
LANE_COLORS = [
    (0, 200, 0),     # Lane 1 - Green
    (0, 150, 255),   # Lane 2 - Orange
    (0, 0, 255),     # Lane 3 - Red
    (255, 200, 0),   # Lane 4 - Cyan
]
LANE_QCOLORS = [
    QColor(0, 200, 0),
    QColor(255, 150, 0),
    QColor(255, 0, 0),
    QColor(0, 200, 255),
]


class ArUcoLaneAssigner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Traffic — ArUco Lane Assignment")
        self.setMinimumSize(950, 600)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QLabel { color: #e0e0e0; }
            QGroupBox { 
                color: #00d4aa; font-weight: bold; font-size: 13px;
                border: 1px solid #333; border-radius: 8px;
                margin-top: 12px; padding-top: 16px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QPushButton {
                background-color: #16213e; color: white; border: 1px solid #0f3460;
                padding: 8px 16px; border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { background-color: #0f3460; }
            QPushButton:pressed { background-color: #00d4aa; color: black; }
            QComboBox {
                background-color: #16213e; color: white; border: 1px solid #0f3460;
                padding: 6px; border-radius: 4px; font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #16213e; color: white; }
            QTableWidget {
                background-color: #16213e; color: white; border: 1px solid #333;
                gridline-color: #333; font-size: 12px;
            }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section {
                background-color: #0f3460; color: #00d4aa; font-weight: bold;
                border: 1px solid #333; padding: 6px;
            }
        """)

        # State
        self.cap = None
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.detected_markers = {}  # id -> corners
        self.assignments = {}       # marker_id (str) -> lane_number (int, 1-4)
        self.load_config()

        # Timer for camera
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)

        self.init_ui()

    def load_config(self):
        """Load existing aruco-lane assignments from config."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    saved = cfg.get("aruco_lane_map", {})
                    self.assignments = {str(k): int(v) for k, v in saved.items()}
            except:
                pass

    def save_config(self):
        """Save aruco-lane assignments to config.json."""
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
            except:
                pass
        cfg["aruco_lane_map"] = {str(k): v for k, v in self.assignments.items()}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # === Left: Camera Feed ===
        left = QVBoxLayout()

        cam_group = QGroupBox("📷 Live Camera Feed")
        cam_layout = QVBoxLayout(cam_group)

        self.video_label = QLabel("Click 'Start Camera' to begin")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(600, 420)
        self.video_label.setStyleSheet("background-color: #111; border-radius: 8px; font-size: 14px; color: #666;")
        cam_layout.addWidget(self.video_label)

        btn_row = QHBoxLayout()
        self.btn_camera = QPushButton("▶ Start Camera")
        self.btn_camera.clicked.connect(self.toggle_camera)
        self.btn_camera.setStyleSheet("QPushButton { background-color: #0f3460; font-size: 13px; padding: 10px; }")
        btn_row.addWidget(self.btn_camera)

        self.btn_snapshot = QPushButton("📸 Detect Markers")
        self.btn_snapshot.clicked.connect(self.detect_now)
        self.btn_snapshot.setStyleSheet("QPushButton { background-color: #1a5276; font-size: 13px; padding: 10px; }")
        btn_row.addWidget(self.btn_snapshot)
        cam_layout.addLayout(btn_row)

        # Status label
        self.status_label = QLabel("Detected markers will appear here")
        self.status_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        cam_layout.addWidget(self.status_label)

        left.addWidget(cam_group)
        main_layout.addLayout(left, stretch=3)

        # === Right: Assignment Panel ===
        right = QVBoxLayout()

        # Detected Markers Table
        detect_group = QGroupBox("🔍 Detected Markers")
        detect_layout = QVBoxLayout(detect_group)

        self.marker_table = QTableWidget(0, 3)
        self.marker_table.setHorizontalHeaderLabels(["Marker ID", "Assign Lane", "Status"])
        self.marker_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.marker_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.marker_table.verticalHeader().setVisible(False)
        detect_layout.addWidget(self.marker_table)

        right.addWidget(detect_group)

        # Saved Assignments
        saved_group = QGroupBox("💾 Saved Assignments")
        saved_layout = QVBoxLayout(saved_group)

        self.saved_table = QTableWidget(0, 2)
        self.saved_table.setHorizontalHeaderLabels(["Marker ID", "Lane #"])
        self.saved_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.saved_table.verticalHeader().setVisible(False)
        saved_layout.addWidget(self.saved_table)

        btn_row2 = QHBoxLayout()
        btn_save = QPushButton("💾 Save All")
        btn_save.clicked.connect(self.save_all)
        btn_save.setStyleSheet("QPushButton { background-color: #1e8449; font-size: 13px; padding: 10px; }")
        btn_row2.addWidget(btn_save)

        btn_clear = QPushButton("🗑 Clear All")
        btn_clear.clicked.connect(self.clear_all)
        btn_clear.setStyleSheet("QPushButton { background-color: #922b21; font-size: 13px; padding: 10px; }")
        btn_row2.addWidget(btn_clear)
        saved_layout.addLayout(btn_row2)

        right.addWidget(saved_group)

        # Lane Legend
        legend_group = QGroupBox("🚦 Lane Colors")
        legend_layout = QVBoxLayout(legend_group)
        for i in range(4):
            lane_label = QLabel(f"  ■  Lane {i+1}")
            lane_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            lane_label.setStyleSheet(f"color: {LANE_QCOLORS[i].name()}; padding: 3px;")
            legend_layout.addWidget(lane_label)
        right.addWidget(legend_group)

        main_layout.addLayout(right, stretch=2)

        # Load saved assignments into table
        self.refresh_saved_table()

    def toggle_camera(self):
        if self.cap and self.cap.isOpened():
            self.preview_timer.stop()
            self.cap.release()
            self.cap = None
            self.btn_camera.setText("▶ Start Camera")
            self.video_label.setText("Camera stopped")
        else:
            cam_source = 2
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE) as f:
                        cfg = json.load(f)
                        src = cfg.get("camera_source", "2")
                        cam_source = int(src) if src.isdigit() else src
                except:
                    pass

            self.cap = cv2.VideoCapture(cam_source)
            if self.cap.isOpened():
                self.btn_camera.setText("⏹ Stop Camera")
                self.preview_timer.start(50)
            else:
                QMessageBox.warning(self, "Camera Error", f"Cannot open camera {cam_source}")

    def update_preview(self):
        if not self.cap or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            return

        # Detect markers on every frame for live preview
        corners, ids, _ = self.detector.detectMarkers(frame)
        display = frame.copy()

        if ids is not None:
            ids_flat = ids.flatten()
            for i, marker_id in enumerate(ids_flat):
                mid = str(int(marker_id))
                pts = corners[i][0].astype(int)

                # Get assigned lane color or default white
                if mid in self.assignments:
                    lane = self.assignments[mid]
                    color = LANE_COLORS[lane - 1]
                    label = f"ID:{mid} -> Lane {lane}"
                else:
                    color = (255, 255, 255)
                    label = f"ID:{mid} (unassigned)"

                # Draw marker outline
                cv2.polylines(display, [pts], True, color, 3)

                # Fill semi-transparent
                overlay = display.copy()
                cv2.fillPoly(overlay, [pts], color)
                cv2.addWeighted(overlay, 0.2, display, 0.8, 0, display)

                # Label
                cx, cy = np.mean(pts, axis=0).astype(int)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                cv2.rectangle(display, (cx - tw//2 - 4, cy - th - 8), (cx + tw//2 + 4, cy + 4), (0, 0, 0), -1)
                cv2.putText(display, label, (cx - tw//2, cy - 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            self.status_label.setText(f"Detecting: {len(ids_flat)} marker(s) visible — IDs: {list(ids_flat)}")
        else:
            self.status_label.setText("No markers detected — show ArUco markers to the camera")

        # Convert to QPixmap
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        scaled = QPixmap.fromImage(qimg).scaled(
            self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.video_label.setPixmap(scaled)

    def detect_now(self):
        """Snapshot current markers and populate the assignment table."""
        if not self.cap or not self.cap.isOpened():
            QMessageBox.warning(self, "No Camera", "Start the camera first!")
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        corners, ids, _ = self.detector.detectMarkers(frame)

        if ids is None or len(ids) == 0:
            QMessageBox.information(self, "No Markers", "No ArUco markers detected. Show markers to the camera.")
            return

        ids_flat = ids.flatten()
        self.detected_markers = {}
        for i, mid in enumerate(ids_flat):
            self.detected_markers[str(int(mid))] = corners[i]

        # Populate table
        self.marker_table.setRowCount(len(ids_flat))
        for row, mid in enumerate(sorted(self.detected_markers.keys(), key=int)):
            # Marker ID
            id_item = QTableWidgetItem(f"  ID: {mid}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            id_item.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            self.marker_table.setItem(row, 0, id_item)

            # Lane combo
            combo = QComboBox()
            combo.addItem("— Select Lane —")
            for lane in range(1, 5):
                combo.addItem(f"Lane {lane}")
            # Pre-select if already assigned
            if mid in self.assignments:
                combo.setCurrentIndex(self.assignments[mid])
            combo.setProperty("marker_id", mid)
            combo.currentIndexChanged.connect(lambda idx, m=mid: self.on_lane_selected(m, idx))
            self.marker_table.setCellWidget(row, 1, combo)

            # Status
            if mid in self.assignments:
                status = QTableWidgetItem(f"  ✅ Lane {self.assignments[mid]}")
                status.setForeground(LANE_QCOLORS[self.assignments[mid] - 1])
            else:
                status = QTableWidgetItem("  ⏳ Pending")
                status.setForeground(QColor(150, 150, 150))
            status.setFlags(status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.marker_table.setItem(row, 2, status)

        self.marker_table.resizeRowsToContents()
        self.statusBar().showMessage(f"Found {len(ids_flat)} markers. Assign lanes and click Save.")

    def on_lane_selected(self, marker_id, lane_index):
        """When user selects a lane for a marker."""
        if lane_index == 0:
            # "Select Lane" chosen, remove assignment
            self.assignments.pop(marker_id, None)
        else:
            self.assignments[marker_id] = lane_index  # 1-4

        # Update status column
        for row in range(self.marker_table.rowCount()):
            id_item = self.marker_table.item(row, 0)
            if id_item and marker_id in id_item.text():
                if marker_id in self.assignments:
                    lane = self.assignments[marker_id]
                    status = QTableWidgetItem(f"  ✅ Lane {lane}")
                    status.setForeground(LANE_QCOLORS[lane - 1])
                else:
                    status = QTableWidgetItem("  ⏳ Pending")
                    status.setForeground(QColor(150, 150, 150))
                status.setFlags(status.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.marker_table.setItem(row, 2, status)
                break

        self.refresh_saved_table()

    def refresh_saved_table(self):
        """Update the saved assignments table."""
        self.saved_table.setRowCount(len(self.assignments))
        for row, (mid, lane) in enumerate(sorted(self.assignments.items(), key=lambda x: int(x[0]))):
            id_item = QTableWidgetItem(f"  Marker {mid}")
            id_item.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.saved_table.setItem(row, 0, id_item)

            lane_item = QTableWidgetItem(f"  Lane {lane}")
            lane_item.setForeground(LANE_QCOLORS[lane - 1])
            lane_item.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            lane_item.setFlags(lane_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.saved_table.setItem(row, 1, lane_item)

    def save_all(self):
        """Save all assignments to config.json."""
        if not self.assignments:
            QMessageBox.warning(self, "Nothing to Save", "Assign at least one marker to a lane first.")
            return
        self.save_config()
        self.refresh_saved_table()
        QMessageBox.information(self, "Saved",
                                f"Saved {len(self.assignments)} marker-lane assignment(s) to config.json!\n\n" +
                                "\n".join([f"  Marker {k} → Lane {v}" for k, v in sorted(self.assignments.items(), key=lambda x: int(x[0]))]))

    def clear_all(self):
        """Clear all assignments."""
        reply = QMessageBox.question(self, "Clear All?", "Remove all marker-lane assignments?")
        if reply == QMessageBox.StandardButton.Yes:
            self.assignments.clear()
            self.marker_table.setRowCount(0)
            self.refresh_saved_table()
            self.save_config()
            self.statusBar().showMessage("All assignments cleared.")

    def closeEvent(self, event):
        self.preview_timer.stop()
        if self.cap and self.cap.isOpened():
            self.cap.release()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = ArUcoLaneAssigner()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
