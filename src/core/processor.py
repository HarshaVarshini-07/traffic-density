from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import numpy as np
import cv2
import json
import os

from src.core.camera import CameraThread
from src.core.detector import VehicleDetector
from src.core.aruco_manager import ArucoManager
from src.core.traffic_logic import TrafficController
from src.core.logger import DataLogger

CONFIG_FILE = "config.json"


class VideoProcessor(QObject):
    """
    Worker object that processes video frames in a background thread.
    Uses the custom-trained YOLO model and ArUco lane mapping.
    """
    processed_signal = pyqtSignal(np.ndarray, list, list)  # frame, densities, light_states
    finished = pyqtSignal()

    def __init__(self, camera_source=0, conf_threshold=0.3):
        super().__init__()
        self.camera_source = camera_source
        self.conf_threshold = conf_threshold
        self.camera = None
        self.detector = None
        self.aruco_manager = None
        self.traffic_controller = None
        self.logger = None
        self.aruco_lane_map = {}  # marker_id -> lane_number
        
        # Load config
        self._load_config()

    def _load_config(self):
        """Load model path and ArUco lane mapping from config."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    self.model_path = cfg.get("model_path", "yolov8n.pt")
                    aruco_map = cfg.get("aruco_lane_map", {})
                    self.aruco_lane_map = {int(k): int(v) for k, v in aruco_map.items()}
                    print(f"Config loaded: model={self.model_path}, aruco_map={self.aruco_lane_map}")
            except Exception as e:
                print(f"Config load error: {e}")
                self.model_path = "yolov8n.pt"
        else:
            self.model_path = "yolov8n.pt"

    @pyqtSlot()
    def start_processing(self):
        try:
            self.detector = VehicleDetector(
                model_path=self.model_path,
                conf_threshold=self.conf_threshold
            )
            self.aruco_manager = ArucoManager()
            self.traffic_controller = TrafficController()
            self.logger = DataLogger()
            
            self.camera = CameraThread(self.camera_source)
            self.camera.frame_received.connect(self.process_frame)
            self.camera.start()
        except Exception as e:
            print(f"Error initializing processor: {e}")

    @pyqtSlot(np.ndarray)
    def process_frame(self, frame):
        try:
            # 1. Detect ArUco markers (using OpenCV directly for reliability)
            aruco_frame = frame.copy()
            self.aruco_manager.detect_markers(frame)
            
            # Check for emergency vehicles via ArUco lane mapping
            emergency_lane = self._check_aruco_emergency(frame)
            
            # 2. Detect ALL objects with custom model
            detections = self.detector.detect(frame)
            
            # 3. Annotate frame with all detections
            annotated = self.detector.annotate(frame, detections, show_all=True)
            
            # 4. Draw ArUco markers with lane labels
            annotated = self._draw_aruco_overlay(annotated)
            
            # 5. Count cars per lane (using quadrant-based approach)
            car_detections = self.detector.get_car_detections(detections)
            h, w, _ = annotated.shape
            cx, cy = w // 2, h // 2
            lane_counts = [0, 0, 0, 0]
            
            if car_detections.xyxy is not None and len(car_detections.xyxy) > 0:
                for box in car_detections.xyxy:
                    bx = (box[0] + box[2]) / 2
                    by = (box[1] + box[3]) / 2
                    
                    if bx < cx and by < cy: lane_counts[0] += 1
                    elif bx >= cx and by < cy: lane_counts[1] += 1
                    elif bx >= cx and by >= cy: lane_counts[2] += 1
                    elif bx < cx and by >= cy: lane_counts[3] += 1
            
            # 6. Traffic light logic (with emergency override)
            if emergency_lane is not None:
                # Emergency: force green on that lane
                states = ['R'] * 4
                states[emergency_lane - 1] = 'G'
                # Draw emergency alert
                cv2.rectangle(annotated, (0, h-50), (w, h), (0, 0, 180), -1)
                cv2.putText(annotated, f"EMERGENCY: Lane {emergency_lane} PRIORITY",
                           (10, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            else:
                states = self.traffic_controller.update(lane_counts)
            
            # 7. Draw lane info overlay
            annotated = self._draw_lane_overlay(annotated, lane_counts, states)
            
            # 8. Log
            if self.logger:
                self.logger.log(lane_counts, states)
            
            self.processed_signal.emit(annotated, lane_counts, states)
            
        except Exception as e:
            print(f"Processing Error: {e}")
            self.processed_signal.emit(frame, [0,0,0,0], ['R']*4)

    def _check_aruco_emergency(self, frame):
        """Check if any recognized ArUco marker is visible → emergency lane."""
        if not self.aruco_lane_map:
            return None
        
        for marker_id, lane_num in self.aruco_lane_map.items():
            if marker_id in self.aruco_manager.marker_corners:
                return lane_num
        return None

    def _draw_aruco_overlay(self, frame):
        """Draw ArUco markers with lane assignments."""
        corners, ids, _ = self.aruco_manager.detector.detectMarkers(frame)
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
            lane_colors = [(0,200,0), (0,150,255), (0,0,255), (255,200,0)]
            for i, marker_id in enumerate(ids.flatten()):
                mid = int(marker_id)
                pts = corners[i][0].astype(int)
                cx, cy = np.mean(pts, axis=0).astype(int)
                
                if mid in self.aruco_lane_map:
                    lane = self.aruco_lane_map[mid]
                    color = lane_colors[lane - 1] if lane <= 4 else (255,255,255)
                    label = f"Lane {lane}"
                    cv2.putText(frame, label, (cx - 30, cy + 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    def _draw_lane_overlay(self, frame, counts, states):
        """Draw lane count and traffic light state info."""
        h, w = frame.shape[:2]
        state_colors = {'G': (0, 200, 0), 'Y': (0, 200, 255), 'R': (0, 0, 200)}
        
        # Top-left info panel
        cv2.rectangle(frame, (5, 5), (200, 115), (0, 0, 0), -1)
        cv2.rectangle(frame, (5, 5), (200, 115), (50, 50, 50), 1)
        cv2.putText(frame, "Lane  Cars  Light", (12, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)
        
        for i in range(4):
            y = 45 + i * 20
            color = state_colors.get(states[i], (200, 200, 200))
            cv2.putText(frame, f"Lane {i+1}:  {counts[i]:>2}    {states[i]}",
                       (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            # Small traffic light circle
            cv2.circle(frame, (185, y - 5), 6, color, -1)
        
        return frame

    @pyqtSlot()
    def stop(self):
        if self.camera:
            self.camera.stop()
        self.finished.emit()
