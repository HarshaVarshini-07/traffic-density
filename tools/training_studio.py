"""
Smart Traffic - Training Studio
================================
A GUI tool for annotating frames and training custom YOLO models.

Features:
- Load video or camera feed
- Capture frames
- Draw bounding boxes with mouse
- Label objects (car, lane_marking, traffic_light, aruco_marker, boundary)
- Save annotations in YOLO format
- Train model with one click

Usage:
    python tools/training_studio.py
"""
import sys
import os
import json
import glob

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'libs'))
sys.path.append(PROJECT_ROOT)

import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QRadioButton,
    QButtonGroup, QGroupBox, QFileDialog, QMessageBox, QProgressBar,
    QFrame, QSplitter, QStatusBar, QSpinBox, QSlider
)
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont, QMouseEvent, QPolygon, QBrush

# --- Configuration ---
TRAINING_DATA_DIR = os.path.join(PROJECT_ROOT, 'tools', 'training_data')
IMAGES_DIR = os.path.join(TRAINING_DATA_DIR, 'images')
LABELS_DIR = os.path.join(TRAINING_DATA_DIR, 'labels')
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'config.json')

# Classes
CLASSES = ['car', 'yellow_strip', 'black_strip', 'traffic_light', 'aruco_marker', 'boundary', 'mixed_lane', 'uno_breadboard', 'emergency_vehicle']
CLASS_COLORS = {
    'car': QColor(0, 255, 100),
    'yellow_strip': QColor(255, 255, 0),
    'black_strip': QColor(80, 80, 80),
    'traffic_light': QColor(255, 100, 100),
    'aruco_marker': QColor(100, 200, 255),
    'boundary': QColor(200, 100, 255),
    'mixed_lane': QColor(255, 165, 0),
    'uno_breadboard': QColor(0, 200, 200),
    'emergency_vehicle': QColor(255, 0, 0),
}

# Ensure directories exist
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(LABELS_DIR, exist_ok=True)


class AnnotationCanvas(QLabel):
    """
    Widget for displaying frames and drawing annotations.
    
    Drawing Modes (automatic):
    - Drag CLOCKWISE → Rectangle bounding box
    - Drag ANTI-CLOCKWISE → Freeform polygon
    """
    box_drawn = pyqtSignal(QRect)
    polygon_drawn = pyqtSignal(list)  # list of QPoint
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 480)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #1a1a2e; border: 2px solid #333; color: #666; font-size: 14px;")
        
        self.original_pixmap = None
        # annotations: list of (shape_data, class_name, shape_type)
        # shape_type: 'rect' or 'poly'
        # shape_data: QRect for 'rect', list of QPoint for 'poly'
        self.boxes = []
        self.current_class = 'car'
        self.drawing = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.draw_path = []  # Track all mouse points during drag
        
        self.setMouseTracking(True)
        self.setText("Draw CLOCKWISE → Rectangle | Draw ANTI-CLOCKWISE → Freeform")

    def set_frame(self, frame):
        """Set a CV2 frame (BGR numpy array) as the display."""
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.original_pixmap = QPixmap.fromImage(q_img)
        self.update_display()

    def set_boxes(self, boxes):
        """Set the list of annotations."""
        self.boxes = boxes
        self.update_display()

    @staticmethod
    def shoelace_sign(points):
        """
        Compute the signed area using the shoelace formula.
        Positive = clockwise, Negative = anti-clockwise (in screen coords where Y is down).
        """
        if len(points) < 3:
            return 0
        # Sample every Nth point for speed
        step = max(1, len(points) // 30)
        sampled = points[::step]
        n = len(sampled)
        if n < 3:
            return 0
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += sampled[i].x() * sampled[j].y()
            area -= sampled[j].x() * sampled[i].y()
        return area

    def update_display(self):
        if self.original_pixmap is None:
            return
        
        display = self.original_pixmap.copy()
        painter = QPainter(display)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw existing annotations
        for annotation in self.boxes:
            if len(annotation) == 3:
                shape_data, class_name, shape_type = annotation
            else:
                # Backward compatibility: (QRect, class_name)
                shape_data, class_name = annotation
                shape_type = 'rect'
            
            color = CLASS_COLORS.get(class_name, QColor(0, 255, 0))
            pen = QPen(color, 2)
            painter.setPen(pen)
            
            if shape_type == 'poly' and isinstance(shape_data, list):
                # Draw polygon
                polygon = QPolygon(shape_data)
                painter.drawPolygon(polygon)
                # Semi-transparent fill
                fill_color = QColor(color)
                fill_color.setAlpha(40)
                painter.setBrush(QBrush(fill_color))
                painter.drawPolygon(polygon)
                painter.setBrush(QBrush())  # Reset brush
                # Label at first point
                if shape_data:
                    label_rect = QRect(shape_data[0].x(), shape_data[0].y() - 20, 130, 20)
                    painter.fillRect(label_rect, QColor(0, 0, 0, 180))
                    painter.setPen(QPen(color))
                    font = QFont("Arial", 10, QFont.Weight.Bold)
                    painter.setFont(font)
                    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, f"⭕ {class_name}")
            else:
                # Draw rectangle
                rect = shape_data
                painter.drawRect(rect)
                label_rect = QRect(rect.x(), rect.y() - 20, 130, 20)
                painter.fillRect(label_rect, QColor(0, 0, 0, 180))
                painter.setPen(QPen(color))
                font = QFont("Arial", 10, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, f"▭ {class_name}")
        
        # Draw current path/box being drawn
        if self.drawing and len(self.draw_path) > 1:
            color = CLASS_COLORS.get(self.current_class, QColor(0, 255, 0))
            
            # Draw the live path
            pen = QPen(color, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(1, len(self.draw_path)):
                painter.drawLine(self.draw_path[i-1], self.draw_path[i])
            
            # Also draw rectangle preview
            rect = QRect(self.start_point, self.end_point).normalized()
            pen_rect = QPen(QColor(255, 255, 255, 100), 1, Qt.PenStyle.DotLine)
            painter.setPen(pen_rect)
            painter.drawRect(rect)
            
            # Show direction hint
            sign = self.shoelace_sign(self.draw_path)
            hint = "▭ RECT (clockwise)" if sign > 0 else "⭕ FREEFORM (anti-clockwise)" if sign < 0 else "..."
            hint_rect = QRect(10, 10, 280, 30)
            painter.fillRect(hint_rect, QColor(0, 0, 0, 200))
            painter.setPen(QPen(QColor(0, 255, 200)))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, hint)
        
        painter.end()
        
        # Scale to fit
        scaled = display.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, 
                               Qt.TransformationMode.FastTransformation)
        self.setPixmap(scaled)

    def get_scale_offset(self):
        """Get the scale and offset for mouse-to-image coordinate conversion."""
        if self.original_pixmap is None:
            return 1.0, 0, 0
        
        pw = self.original_pixmap.width()
        ph = self.original_pixmap.height()
        ww = self.width()
        wh = self.height()
        
        scale = min(ww / pw, wh / ph)
        offset_x = (ww - pw * scale) / 2
        offset_y = (wh - ph * scale) / 2
        
        return scale, offset_x, offset_y

    def widget_to_image(self, pos):
        """Convert widget coordinates to image coordinates."""
        scale, ox, oy = self.get_scale_offset()
        if scale == 0:
            return QPoint(0, 0)
        x = int((pos.x() - ox) / scale)
        y = int((pos.y() - oy) / scale)
        return QPoint(x, y)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.original_pixmap:
            self.drawing = True
            self.start_point = self.widget_to_image(event.pos())
            self.end_point = self.start_point
            self.draw_path = [self.start_point]

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing:
            pt = self.widget_to_image(event.pos())
            self.end_point = pt
            self.draw_path.append(pt)
            # Throttle display updates (every 3rd point)
            if len(self.draw_path) % 3 == 0:
                self.update_display()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            self.end_point = self.widget_to_image(event.pos())
            self.draw_path.append(self.end_point)
            
            # Determine direction
            sign = self.shoelace_sign(self.draw_path)
            
            if sign > 0:
                # CLOCKWISE → Rectangle
                rect = QRect(self.start_point, self.end_point).normalized()
                if rect.width() > 10 and rect.height() > 10:
                    self.boxes.append((rect, self.current_class, 'rect'))
                    self.box_drawn.emit(rect)
            else:
                # ANTI-CLOCKWISE → Freeform polygon
                # Simplify path (keep every Nth point)
                step = max(1, len(self.draw_path) // 20)
                simplified = self.draw_path[::step]
                if len(simplified) >= 3:
                    self.boxes.append((simplified, self.current_class, 'poly'))
                    # Emit bounding rect for the list
                    xs = [p.x() for p in simplified]
                    ys = [p.y() for p in simplified]
                    bounding = QRect(min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys))
                    self.box_drawn.emit(bounding)
            
            self.draw_path = []
            self.update_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()


class TrainingStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Traffic - Training Studio")
        self.resize(1200, 800)
        self.setStyleSheet(STUDIO_STYLE)
        
        self.cap = None
        self.current_frame = None
        self.frame_index = 0
        self.captured_frames = []  # List of (filename, frame)
        self.current_image_idx = -1
        
        self.setup_ui()
        self.load_existing_data()
        self.statusBar().showMessage("Ready. Load a video or use camera to capture frames.")

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # --- Left: Canvas ---
        left_panel = QVBoxLayout()
        
        self.canvas = AnnotationCanvas()
        left_panel.addWidget(self.canvas, stretch=5)
        
        # Video controls
        video_controls = QHBoxLayout()
        self.btn_load_video = QPushButton("📂 Load Video")
        self.btn_load_video.clicked.connect(self.load_video)
        video_controls.addWidget(self.btn_load_video)
        
        self.btn_camera = QPushButton("📷 Use Camera")
        self.btn_camera.clicked.connect(self.use_camera)
        video_controls.addWidget(self.btn_camera)
        
        self.btn_resume = QPushButton("▶ Resume Camera")
        self.btn_resume.clicked.connect(self.resume_camera)
        video_controls.addWidget(self.btn_resume)
        
        self.btn_capture = QPushButton("📸 Capture Frame")
        self.btn_capture.clicked.connect(self.capture_frame)
        self.btn_capture.setObjectName("ActionBtn")
        video_controls.addWidget(self.btn_capture)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.valueChanged.connect(self.seek_video)
        video_controls.addWidget(self.slider)
        
        left_panel.addLayout(video_controls)
        
        # Navigation
        nav_controls = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.clicked.connect(self.prev_image)
        nav_controls.addWidget(self.btn_prev)
        
        self.lbl_counter = QLabel("0 / 0")
        self.lbl_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_counter.setStyleSheet("font-size: 14px; font-weight: bold; color: #00ADB5;")
        nav_controls.addWidget(self.lbl_counter)
        
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self.next_image)
        nav_controls.addWidget(self.btn_next)
        
        left_panel.addLayout(nav_controls)
        main_layout.addLayout(left_panel, stretch=3)
        
        # --- Right: Controls ---
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)
        
        # Class selector
        class_group = QGroupBox("Object Class")
        class_layout = QVBoxLayout()
        self.class_buttons = QButtonGroup()
        
        for i, cls in enumerate(CLASSES):
            rb = QRadioButton(f"  {cls}")
            rb.setStyleSheet(f"color: {CLASS_COLORS[cls].name()}; font-size: 13px;")
            if i == 0:
                rb.setChecked(True)
            self.class_buttons.addButton(rb, i)
            class_layout.addWidget(rb)
        
        self.class_buttons.idClicked.connect(self.change_class)
        class_group.setLayout(class_layout)
        right_panel.addWidget(class_group)
        
        # Hotkeys info
        hotkey_label = QLabel("Hotkeys: 1-9 to select class\nDraw: Click + Drag on frame")
        hotkey_label.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
        right_panel.addWidget(hotkey_label)
        
        # Annotations list
        ann_group = QGroupBox("Annotations (this frame)")
        ann_layout = QVBoxLayout()
        self.ann_list = QListWidget()
        self.ann_list.setMaximumHeight(200)
        ann_layout.addWidget(self.ann_list)
        
        self.btn_delete_box = QPushButton("🗑 Delete Selected Box")
        self.btn_delete_box.clicked.connect(self.delete_selected_box)
        ann_layout.addWidget(self.btn_delete_box)
        
        self.btn_clear = QPushButton("Clear All Boxes")
        self.btn_clear.clicked.connect(self.clear_boxes)
        ann_layout.addWidget(self.btn_clear)
        
        ann_group.setLayout(ann_layout)
        right_panel.addWidget(ann_group)
        
        # Save / Train
        self.btn_save = QPushButton("💾 Save Annotations")
        self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.save_annotations)
        right_panel.addWidget(self.btn_save)
        
        self.btn_save_all = QPushButton("💾 Save All & Generate YAML")
        self.btn_save_all.clicked.connect(self.save_all_and_generate_yaml)
        right_panel.addWidget(self.btn_save_all)
        
        self.btn_train = QPushButton("🚀 Train Model")
        self.btn_train.setStyleSheet("background-color: #BB86FC; color: black; font-weight: bold; padding: 10px;")
        self.btn_train.clicked.connect(self.train_model)
        right_panel.addWidget(self.btn_train)
        
        # Stats
        self.lbl_stats = QLabel("Images: 0 | Labeled: 0")
        self.lbl_stats.setStyleSheet("color: #888; padding: 5px;")
        right_panel.addWidget(self.lbl_stats)
        
        right_panel.addStretch()
        main_layout.addLayout(right_panel, stretch=1)
        
        # Canvas callback
        self.canvas.box_drawn.connect(self.on_box_drawn)
        
        # Timer for video preview
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.preview_next_frame)

    def keyPressEvent(self, event):
        """Hotkeys for class selection."""
        key = event.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(CLASSES):
                self.class_buttons.button(idx).setChecked(True)
                self.change_class(idx)

    def change_class(self, idx):
        self.canvas.current_class = CLASSES[idx]
        self.statusBar().showMessage(f"Selected class: {CLASSES[idx]}")

    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Video", PROJECT_ROOT, 
                                               "Videos (*.mp4 *.avi *.mkv);;All Files (*)")
        if path:
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(path)
            total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.slider.setRange(0, max(1, total - 1))
            self.preview_timer.start(50)
            self.statusBar().showMessage(f"Loaded: {os.path.basename(path)} ({total} frames)")

    def use_camera(self):
        # Load camera source from config
        cam_source = 0
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    src = cfg.get("camera_source", "0")
                    cam_source = int(src) if src.isdigit() else src
            except:
                pass
        
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(cam_source)
        self.preview_timer.start(33)
        self.statusBar().showMessage(f"Camera {cam_source} opened")

    def preview_next_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame
                # Only update canvas if not drawing (avoids lag while annotating)
                if not self.canvas.drawing:
                    self.canvas.set_frame(frame)
                self.frame_index = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def seek_video(self, value):
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, value)

    def capture_frame(self):
        if self.current_frame is None:
            QMessageBox.warning(self, "No Frame", "Load a video or camera first.")
            return
        
        # Pause preview so user can annotate this frame
        self.preview_timer.stop()
        
        # Save the frozen frame
        frozen_frame = self.current_frame.copy()
        idx = len(glob.glob(os.path.join(IMAGES_DIR, "*.jpg")))
        filename = f"frame_{idx:04d}.jpg"
        filepath = os.path.join(IMAGES_DIR, filename)
        cv2.imwrite(filepath, frozen_frame)
        
        self.captured_frames.append(filename)
        self.current_image_idx = len(self.captured_frames) - 1
        
        # Reset boxes for new frame
        self.canvas.boxes = []
        self.ann_list.clear()
        self.canvas.set_frame(frozen_frame)
        
        self.update_counter()
        self.statusBar().showMessage(f"Captured: {filename} — Annotate now, then click 'Resume Camera' for more.")

    def resume_camera(self):
        """Resume live camera feed after annotating."""
        if self.cap and self.cap.isOpened():
            # Auto-save current annotations before resuming
            if self.canvas.boxes and self.current_image_idx >= 0:
                self.save_annotations()
            self.preview_timer.start(50)
            self.statusBar().showMessage("Camera resumed. Click 'Capture Frame' to snap another.")
        else:
            QMessageBox.warning(self, "No Camera", "Click 'Use Camera' first.")

    def load_existing_data(self):
        """Load previously saved images."""
        existing = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.jpg")))
        self.captured_frames = [os.path.basename(f) for f in existing]
        if self.captured_frames:
            self.current_image_idx = 0
            self.load_image_at_index(0)
        self.update_counter()
        self.update_stats()

    def load_image_at_index(self, idx):
        if 0 <= idx < len(self.captured_frames):
            self.preview_timer.stop()
            filepath = os.path.join(IMAGES_DIR, self.captured_frames[idx])
            frame = cv2.imread(filepath)
            if frame is not None:
                self.current_frame = frame
                self.canvas.set_frame(frame)
                self.current_image_idx = idx
                
                # Load existing annotations
                self.load_annotations_for_image(self.captured_frames[idx])
                self.update_counter()

    def load_annotations_for_image(self, filename):
        """Load YOLO format annotations for an image (supports both bbox and polygon)."""
        label_file = os.path.join(LABELS_DIR, filename.replace('.jpg', '.txt'))
        self.canvas.boxes = []
        self.ann_list.clear()
        
        if os.path.exists(label_file):
            img_h, img_w = self.current_frame.shape[:2]
            with open(label_file) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    cls_id = int(parts[0])
                    cls_name = CLASSES[cls_id] if cls_id < len(CLASSES) else 'unknown'
                    
                    if len(parts) == 5:
                        # Standard YOLO bbox: cls cx cy w h
                        cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        x = int((cx - bw/2) * img_w)
                        y = int((cy - bh/2) * img_h)
                        w = int(bw * img_w)
                        h = int(bh * img_h)
                        self.canvas.boxes.append((QRect(x, y, w, h), cls_name, 'rect'))
                        self.ann_list.addItem(f"▭ {cls_name}: ({x},{y},{w},{h})")
                    else:
                        # YOLO segmentation: cls x1 y1 x2 y2 ... xN yN
                        coords = [float(v) for v in parts[1:]]
                        points = []
                        for i in range(0, len(coords) - 1, 2):
                            px = int(coords[i] * img_w)
                            py = int(coords[i+1] * img_h)
                            points.append(QPoint(px, py))
                        if len(points) >= 3:
                            self.canvas.boxes.append((points, cls_name, 'poly'))
                            self.ann_list.addItem(f"⭕ {cls_name}: ({len(points)} pts)")
        
        self.canvas.update_display()

    def prev_image(self):
        if self.current_image_idx > 0:
            self.load_image_at_index(self.current_image_idx - 1)

    def next_image(self):
        if self.current_image_idx < len(self.captured_frames) - 1:
            self.load_image_at_index(self.current_image_idx + 1)

    def on_box_drawn(self, rect):
        cls = self.canvas.current_class
        # Check if the last annotation is a polygon or rectangle
        if self.canvas.boxes:
            last = self.canvas.boxes[-1]
            if len(last) == 3 and last[2] == 'poly':
                pts = len(last[0])
                self.ann_list.addItem(f"⭕ {cls}: ({pts} pts)")
                self.statusBar().showMessage(f"Added freeform {cls}")
                return
        self.ann_list.addItem(f"▭ {cls}: ({rect.x()},{rect.y()},{rect.width()},{rect.height()})")
        self.statusBar().showMessage(f"Added rectangle {cls}")

    def delete_selected_box(self):
        row = self.ann_list.currentRow()
        if row >= 0 and row < len(self.canvas.boxes):
            self.canvas.boxes.pop(row)
            self.ann_list.takeItem(row)
            self.canvas.update_display()

    def clear_boxes(self):
        self.canvas.boxes = []
        self.ann_list.clear()
        self.canvas.update_display()

    def save_annotations(self):
        """Save annotations in YOLO format (bbox or segmentation polygon)."""
        if self.current_image_idx < 0 or self.current_frame is None:
            return
        
        filename = self.captured_frames[self.current_image_idx]
        label_file = os.path.join(LABELS_DIR, filename.replace('.jpg', '.txt'))
        
        img_h, img_w = self.current_frame.shape[:2]
        
        with open(label_file, 'w') as f:
            for annotation in self.canvas.boxes:
                if len(annotation) == 3:
                    shape_data, cls_name, shape_type = annotation
                else:
                    shape_data, cls_name = annotation
                    shape_type = 'rect'
                
                cls_id = CLASSES.index(cls_name) if cls_name in CLASSES else 0
                
                if shape_type == 'poly' and isinstance(shape_data, list):
                    # YOLO segmentation format: cls x1 y1 x2 y2 ... xN yN
                    coords = []
                    for pt in shape_data:
                        coords.append(f"{pt.x() / img_w:.6f}")
                        coords.append(f"{pt.y() / img_h:.6f}")
                    f.write(f"{cls_id} {' '.join(coords)}\n")
                else:
                    # Standard YOLO bbox format: cls cx cy w h
                    rect = shape_data
                    cx = (rect.x() + rect.width() / 2) / img_w
                    cy = (rect.y() + rect.height() / 2) / img_h
                    bw = rect.width() / img_w
                    bh = rect.height() / img_h
                    f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        
        self.update_stats()
        self.statusBar().showMessage(f"Saved {len(self.canvas.boxes)} annotations to {label_file}")

    def save_all_and_generate_yaml(self):
        """Save current annotations and generate data.yaml for training."""
        self.save_annotations()
        
        # Generate data.yaml
        yaml_path = os.path.join(TRAINING_DATA_DIR, 'data.yaml')
        with open(yaml_path, 'w') as f:
            f.write(f"path: {TRAINING_DATA_DIR}\n")
            f.write(f"train: images\n")
            f.write(f"val: images\n")
            f.write(f"nc: {len(CLASSES)}\n")
            f.write(f"names: {CLASSES}\n")
        
        self.statusBar().showMessage(f"Saved data.yaml with {len(CLASSES)} classes")
        QMessageBox.information(self, "Saved", 
            f"Training data saved!\n\n"
            f"Images: {IMAGES_DIR}\n"
            f"Labels: {LABELS_DIR}\n"
            f"Config: {yaml_path}\n\n"
            f"Total images: {len(self.captured_frames)}")

    def train_model(self):
        """Trigger YOLO training."""
        yaml_path = os.path.join(TRAINING_DATA_DIR, 'data.yaml')
        
        if not os.path.exists(yaml_path):
            QMessageBox.warning(self, "No Data", "Please save annotations and generate YAML first.")
            return
        
        labeled = len(glob.glob(os.path.join(LABELS_DIR, "*.txt")))
        if labeled < 5:
            QMessageBox.warning(self, "Not Enough Data", 
                f"You have {labeled} labeled images. Need at least 5 for training.")
            return
        
        # Show training command
        cmd = f"yolo detect train data={yaml_path} model=yolov8n.pt epochs=50 imgsz=640"
        
        reply = QMessageBox.question(self, "Start Training?",
            f"Ready to train with {labeled} images.\n\n"
            f"Command:\n{cmd}\n\n"
            f"This may take several minutes. Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # Try to run training
            try:
                import subprocess
                self.statusBar().showMessage("Training started... Check terminal for progress.")
                
                # Add libs to PYTHONPATH for the subprocess
                env = os.environ.copy()
                libs_path = os.path.join(PROJECT_ROOT, 'libs')
                env["PYTHONPATH"] = libs_path + os.pathsep + env.get("PYTHONPATH", "")
                
                subprocess.Popen(
                    f'python -m ultralytics detect train data="{yaml_path}" model=yolov8n.pt epochs=50 imgsz=640',
                    shell=True, cwd=PROJECT_ROOT, env=env
                )
            except Exception as e:
                QMessageBox.critical(self, "Training Error", 
                    f"Could not start training:\n{e}\n\n"
                    f"Try running manually:\n{cmd}")

    def update_counter(self):
        total = len(self.captured_frames)
        current = self.current_image_idx + 1 if total > 0 else 0
        self.lbl_counter.setText(f"{current} / {total}")

    def update_stats(self):
        total_images = len(glob.glob(os.path.join(IMAGES_DIR, "*.jpg")))
        total_labels = len(glob.glob(os.path.join(LABELS_DIR, "*.txt")))
        self.lbl_stats.setText(f"Images: {total_images} | Labeled: {total_labels}")

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        self.preview_timer.stop()
        event.accept()


# --- Stylesheet ---
STUDIO_STYLE = """
QMainWindow {
    background-color: #121212;
}
QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: 'Segoe UI', Arial;
}
QGroupBox {
    border: 1px solid #333;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 15px;
    font-weight: bold;
    color: #00ADB5;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border: 1px solid #444;
    border-radius: 6px;
    padding: 8px 15px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3D3D3D;
    border-color: #00ADB5;
}
QPushButton#ActionBtn {
    background-color: #00ADB5;
    color: #000;
    font-weight: bold;
}
QPushButton#ActionBtn:hover {
    background-color: #00C9D4;
}
QListWidget {
    background-color: #1E1E1E;
    border: 1px solid #333;
    border-radius: 4px;
    color: #E0E0E0;
}
QListWidget::item:selected {
    background-color: #00ADB5;
    color: #000;
}
QRadioButton {
    spacing: 8px;
    font-size: 13px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #333;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #00ADB5;
    border: 1px solid #00ADB5;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QStatusBar {
    background-color: #1E1E1E;
    color: #888;
}
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Smart Traffic - Training Studio")
    window = TrainingStudio()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
