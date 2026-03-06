from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
import numpy as np
import cv2
import json
import os
import time

from src.core.camera import CameraThread
from src.core.detector import VehicleDetector
from src.core.aruco_manager import ArucoManager
from src.core.traffic_logic import TrafficController
from src.core.logger import DataLogger
from src.core.esp32_bridge import ESP32Bridge
import threading

CONFIG_FILE = "config.json"


class VideoProcessor(QObject):
    """
    Two-phase processor:
      CALIBRATING: Wait for all 4 ArUco markers, show calibration overlay.
      RUNNING: Lock marker positions, run YOLO + traffic logic.
    """
    processed_signal = pyqtSignal(np.ndarray, list, list)
    model_info_signal = pyqtSignal(dict)
    esp32_status_signal = pyqtSignal(dict)
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
        self.esp32_bridge = None
        self.aruco_lane_map = {}
        self.aruco_boundary_map = {}
        
        # --- Phase control ---
        self._phase = "CALIBRATING"  # CALIBRATING -> RUNNING
        self._locked_marker_positions = {}  # lane_num -> (x, y)
        self._locked_boundary_positions = {} # b_type -> (x, y)
        self._locked_center = None
        self._required_markers = 4
        
        # Frame-skip for YOLO
        self._frame_count = 0
        self._detect_every_n = 3  # Increased from 2 to 3 for better FPS
        self._last_detections = None
        self._last_lane_counts = [0, 0, 0, 0]
        
        # Async YOLO Threading
        self._is_detecting = False
        self._detection_lock = threading.Lock()
        
        # Polling timer for pulling frames
        self._poll_timer = None
        
        # Rolling average for stable lane counts
        self._count_history = []
        self._smooth_window = 5
        
        # Sticky emergency: hold emergency for minimum duration
        # Sticky emergency: hold for minimum duration
        self._emergency_lanes = {}  # {lane_num: last_seen_time}
        self._emergency_hold_time = 2  # Reduce to 2 seconds to clear quickly
        
        # ESP32 optimization
        self._last_sent_counts = None
        self._last_sent_states = None
        self._last_sent_emergency = 0
        
        self._load_config()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    self.model_path = cfg.get("model_path", "yolov8n.pt")
                    aruco_map = cfg.get("aruco_lane_map", {})
                    self.aruco_lane_map = {int(k): int(v) for k, v in aruco_map.items()}
                    bound_map = cfg.get("aruco_boundary_map", {})
                    self.aruco_boundary_map = {int(k): str(v) for k, v in bound_map.items()}
                    
                    self.esp32_port = cfg.get("esp32_port", "COM3")
                    self.esp32_baud = cfg.get("esp32_baud", 115200)
                    self.esp32_enabled = cfg.get("esp32_enabled", False)
                    self._required_markers = len(self.aruco_lane_map)
                    print(f"Config loaded: model={self.model_path}, aruco_map={self.aruco_lane_map}")
                    print(f"Need {self._required_markers} ArUco markers to start")
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
            
            self.esp32_bridge = ESP32Bridge(
                port=getattr(self, 'esp32_port', 'COM3'),
                baud=getattr(self, 'esp32_baud', 115200),
                enabled=getattr(self, 'esp32_enabled', False)
            )
            if self.esp32_bridge.enabled:
                self.esp32_bridge.connect()
                self.esp32_status_signal.emit(self.esp32_bridge.status)
            
            self.model_info_signal.emit(self.detector.model_info)
            
            self.camera = CameraThread(self.camera_source)
            self.camera.start()
            
            # Use a timer to pull frames instead of blocking on signals
            self._poll_timer = QTimer(self)
            self._poll_timer.timeout.connect(self._pull_frame)
            self._poll_timer.start(30)  # ~33fps polling rate
            
        except Exception as e:
            print(f"Error initializing processor: {e}")

    @pyqtSlot()
    def _pull_frame(self):
        """Actively pull the latest frame from the camera thread to avoid queue lag."""
        if not self.camera: return
        frame = self.camera.get_latest_frame()
        if frame is not None:
            self.process_frame(frame)

    def process_frame(self, frame):
        if self._phase == "CALIBRATING":
            self._calibration_frame(frame)
        else:
            self._running_frame(frame)

    def _calibration_frame(self, frame):
        """Phase 1: Detect ArUco markers. Lock when all 4 found."""
        try:
            h, w, _ = frame.shape
            self.aruco_manager.detect_markers(frame)
            
            # Draw detected markers
            corners = self.aruco_manager.last_corners
            ids = self.aruco_manager.last_ids
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
            # Check which lane markers are found
            found_lanes = {}
            for marker_id, lane_num in self.aruco_lane_map.items():
                if marker_id in self.aruco_manager.marker_corners:
                    found_lanes[lane_num] = self.aruco_manager.marker_corners[marker_id]
                    
            # Check which boundary markers are found
            found_bounds = {}
            for marker_id, b_type in self.aruco_boundary_map.items():
                if marker_id in self.aruco_manager.marker_corners:
                    found_bounds[b_type] = self.aruco_manager.marker_corners[marker_id]
            
            found_count = len(found_lanes)
            lane_names = {1: "SOUTH", 2: "EAST", 3: "NORTH", 4: "WEST"}
            
            # Draw calibration overlay
            # Dark overlay bar at top
            cv2.rectangle(frame, (0, 0), (w, 80), (0, 0, 0), -1)
            
            # --- Draw 90x40 Alignment Guide Box ---
            guide_w = int(w * 0.65)
            guide_h = int(guide_w * (40.0 / 90.0))
            cx, cy = w // 2, h // 2
            tl = (cx - guide_w // 2, cy - guide_h // 2)
            br = (cx + guide_w // 2, cy + guide_h // 2)
            
            # Draw semi-transparent dashed/dotted-style line (actually a distinct solid box)
            cv2.rectangle(frame, tl, br, (255, 255, 0), 2, lineType=cv2.LINE_AA)
            cv2.putText(frame, "Align 90x40 Boundary Here", (tl[0], tl[1] - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            cv2.putText(frame, "CALIBRATING - Position all ArUco markers",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            cv2.putText(frame, f"Markers found: {found_count}/{self._required_markers}",
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            # Show status of each lane marker
            x_offset = 350
            for lane_num in sorted(self.aruco_lane_map.values()):
                name = lane_names.get(lane_num, f"L{lane_num}")
                if lane_num in found_lanes:
                    color = (0, 255, 0)
                    status = "OK"
                else:
                    color = (0, 0, 255)
                    status = "?"
                cv2.putText(frame, f"{name}:{status}", (x_offset, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                x_offset += 80
            
            # Draw found marker positions with labels (lanes)
            for lane_num, pos in found_lanes.items():
                px, py = int(pos[0]), int(pos[1])
                name = lane_names.get(lane_num, f"L{lane_num}")
                cv2.circle(frame, (px, py), 12, (0, 255, 0), 2)
                cv2.putText(frame, name, (px - 20, py - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                           
            # Draw found marker positions with labels (boundaries)
            for b_type, pos in found_bounds.items():
                px, py = int(pos[0]), int(pos[1])
                name = b_type.replace("B_", "")
                cv2.circle(frame, (px, py), 12, (200, 200, 200), 2)
                cv2.putText(frame, name, (px - 20, py - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2)
            
            # If all lane markers found -> LOCK and transition to RUNNING
            if found_count >= self._required_markers:
                self._locked_marker_positions = {k: v.copy() for k, v in found_lanes.items()}
                self._locked_boundary_positions = {k: v.copy() for k, v in found_bounds.items()}
                all_pts = np.array(list(self._locked_marker_positions.values()))
                self._locked_center = np.mean(all_pts, axis=0).astype(int)
                self._phase = "RUNNING"
                print(f"Calibration complete! Locked {found_count} lanes and {len(found_bounds)} boundaries.")
                print(f"Locked positions: {self._locked_marker_positions}")
                print(f"Intersection center: {self._locked_center}")
            
            self.processed_signal.emit(frame, [0, 0, 0, 0], ['R'] * 4)
            
        except Exception as e:
            print(f"Calibration Error: {e}")
            self.processed_signal.emit(frame, [0, 0, 0, 0], ['R'] * 4)

    def _running_frame(self, frame):
        """Phase 2: YOLO detection + traffic logic using locked marker positions."""
        try:
            self._frame_count += 1
            h, w, _ = frame.shape
            
            # Use LOCKED marker positions (no more ArUco detection needed)
            marker_positions = self._locked_marker_positions
            center = self._locked_center
            
            emergency_lane = None
            
            # YOLO detection with frame-skip and async thread
            run_yolo = (self._frame_count % self._detect_every_n == 0) or (self._last_detections is None)
            
            if run_yolo and not self._is_detecting:
                # Kick off detection in a background thread so the GUI doesn't stutter
                self._is_detecting = True
                threading.Thread(target=self._run_yolo_async, args=(frame.copy(), marker_positions), daemon=True).start()
                
            # Use the latest available detections while we wait for new ones
            with self._detection_lock:
                detections = self._last_detections
                lane_counts = self._last_lane_counts
            
            # If no detections yet, just draw empty and return
            if detections is None:
                self.processed_signal.emit(frame, [0,0,0,0], ['R']*4)
                return

            # Compute emergency stuff from the LAST known detections so GUI stays smooth
            car_detections = self.detector.get_car_detections(detections)
                
            # Emergency vehicle via current detections
            emg = self.detector.get_emergency_detections(detections)
            detected_emg_lanes = set()
            if emg is not None:
                for box in emg.xyxy:
                    ex = (box[0] + box[2]) / 2
                    ey = (box[1] + box[3]) / 2
                    emg_pt = np.array([ex, ey])
                    best_lane = None
                    best_dist = float('inf')
                    for lane_num, mpos in marker_positions.items():
                        dist = np.linalg.norm(emg_pt - mpos)
                        if dist < best_dist:
                            best_dist = dist
                            best_lane = lane_num
                    if best_lane is not None:
                        detected_emg_lanes.add(best_lane)
            
            
            # Sticky emergency: hold per-lane for minimum duration
            now = time.time()
            
            # Update timers for detected lanes
            for lane in detected_emg_lanes:
                self._emergency_lanes[lane] = now
            
            # Remove expired lanes
            expired = [lane for lane, t in self._emergency_lanes.items()
                       if (now - t) >= self._emergency_hold_time]
            for lane in expired:
                del self._emergency_lanes[lane]
            
            # Pick the best emergency lane: highest density among active emergency lanes
            active_emg_lanes = list(self._emergency_lanes.keys())
            if active_emg_lanes:
                # Sort by density (highest first) — most efficient lane gets green
                best_emg = max(active_emg_lanes, key=lambda l: lane_counts[l - 1])
                emergency_lane = best_emg
            else:
                emergency_lane = None
            
            # Annotate (cars + emergency only)
            annotated = self.detector.annotate(frame, detections, show_all=True)
            
            # Traffic light logic
            if emergency_lane is not None:
                # 0-indexed for traffic controller
                states = self.traffic_controller.update(lane_counts, emergency_lane - 1)
                cv2.rectangle(annotated, (0, h-50), (w, h), (0, 0, 180), -1)
                cv2.putText(annotated, f"EMERGENCY: Lane {emergency_lane} PRIORITY",
                           (10, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            else:
                states = self.traffic_controller.update(lane_counts, None)
            
            # Draw lane overlay using LOCKED positions
            annotated = self._draw_lane_overlay(annotated, lane_counts, states, marker_positions, center, self._locked_boundary_positions)
            
            # Log
            if self.logger:
                self.logger.log(lane_counts, states)
            
            # ESP32 - Only send if data changed to avoid serial bottleneck
            if self.esp32_bridge and self.esp32_bridge.enabled:
                if self._last_sent_counts != lane_counts:
                    self.esp32_bridge.send_density(lane_counts)
                    self._last_sent_counts = lane_counts.copy()
                
                # Handle emergency signal sending
                current_emg = emergency_lane if emergency_lane is not None else 0
                if self._last_sent_emergency != current_emg:
                    self.esp32_bridge.send_emergency(current_emg)
                    self._last_sent_emergency = current_emg
                
                # Send the actual traffic light states to the hardware
                if self._last_sent_states != states:
                    self.esp32_bridge.send_states(states)
                    self._last_sent_states = states.copy()
            
            self.processed_signal.emit(annotated, lane_counts, states)
            
        except Exception as e:
            print(f"Processing Error: {e}")
            self.processed_signal.emit(frame, [0,0,0,0], ['R']*4)

    def _run_yolo_async(self, frame_copy, marker_positions):
        """Runs YOLO on a background thread so GUI doesn't stall."""
        try:
            detections = self.detector.detect(frame_copy)
            car_detections = self.detector.get_car_detections(detections)
            raw_counts = [0, 0, 0, 0]
            
            if car_detections.xyxy is not None and len(car_detections.xyxy) > 0:
                for box in car_detections.xyxy:
                    bx = (box[0] + box[2]) / 2
                    by = (box[1] + box[3]) / 2
                    car_pt = np.array([bx, by])
                    
                    best_lane = None
                    best_dist = float('inf')
                    for lane_num, mpos in marker_positions.items():
                        dist = np.linalg.norm(car_pt - mpos)
                        if dist < best_dist:
                            best_dist = dist
                            best_lane = lane_num
                    if best_lane is not None and 1 <= best_lane <= 4:
                        raw_counts[best_lane - 1] += 1
            
            with self._detection_lock:
                self._last_detections = detections
                
                self._count_history.append(raw_counts)
                if len(self._count_history) > self._smooth_window:
                    self._count_history.pop(0)
                avg = np.mean(self._count_history, axis=0)
                self._last_lane_counts = [int(round(v)) for v in avg]
                
        except Exception as e:
            print(f"Async YOLO thread crashed: {e}")
            
        finally:
            self._is_detecting = False

    def _draw_lane_overlay(self, frame, counts, states, marker_positions, center, boundary_positions):
        """Draw lane zones using locked marker positions."""
        h, w = frame.shape[:2]
        cx, cy = int(center[0]), int(center[1])
        
        # Draw physical boundary polygon and coords if available
        if boundary_positions:
            bound_coords = {
                "B_TL": "(0, 40)",
                "B_TR": "(90, 40)",
                "B_BR": "(90, 0)",
                "B_BL": "(0, 0)"
            }
            order = ["B_TL", "B_TR", "B_BR", "B_BL"]
            valid_pts = []
            for b_type in order:
                if b_type in boundary_positions:
                    valid_pts.append(boundary_positions[b_type])
            
            if len(valid_pts) > 1:
                cv2.polylines(frame, [np.array(valid_pts, dtype=np.int32)], isClosed=True, color=(10, 10, 10), thickness=3)
            
            for b_type, pt in boundary_positions.items():
                px, py = int(pt[0]), int(pt[1])
                cv2.circle(frame, (px, py), 6, (10, 10, 10), -1)
                text = bound_coords.get(b_type, b_type)
                cv2.putText(frame, text, (px - 25, py - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        lane_names = {1: "SOUTH", 2: "EAST", 3: "NORTH", 4: "WEST"}
        lane_colors = {
            1: (0, 140, 255),   # Orange
            2: (0, 200, 0),     # Green
            3: (200, 180, 0),   # Cyan
            4: (180, 0, 255),   # Pink
        }
        state_colors = {'G': (0, 255, 0), 'Y': (0, 255, 255), 'R': (0, 0, 255)}
        
        # Sort markers by angle from center
        marker_angles = []
        for lane_num, mpos in marker_positions.items():
            angle = np.arctan2(mpos[1] - cy, mpos[0] - cx)
            marker_angles.append((angle, lane_num, mpos))
        marker_angles.sort(key=lambda x: x[0])
        
        # Sector boundaries
        n = len(marker_angles)
        for i in range(n):
            angle1 = marker_angles[i][0]
            angle2 = marker_angles[(i + 1) % n][0]
            if angle2 > angle1:
                mid_angle = (angle1 + angle2) / 2
            else:
                mid_angle = (angle1 + angle2 + 2 * np.pi) / 2
            line_len = int(max(w, h) * 0.7)
            ex = int(cx + line_len * np.cos(mid_angle))
            ey = int(cy + line_len * np.sin(mid_angle))
            cv2.line(frame, (cx, cy), (ex, ey), (100, 100, 100), 1)
        
        # Lane lines and labels
        for angle, lane_num, mpos in marker_angles:
            color = lane_colors.get(lane_num, (255, 255, 255))
            mx, my = int(mpos[0]), int(mpos[1])
            
            line_len = int(max(w, h) * 0.7)
            ex = int(cx + line_len * np.cos(angle))
            ey = int(cy + line_len * np.sin(angle))
            cv2.line(frame, (cx, cy), (ex, ey), color, 2)
            
            # Locked marker dot
            cv2.circle(frame, (mx, my), 8, color, -1)
            cv2.circle(frame, (mx, my), 10, color, 2)
            
            # Lane label (reduced size)
            name = lane_names.get(lane_num, f"L{lane_num}")
            text = f"{name}: {counts[lane_num - 1]}"
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            tx = int(cx + (mx - cx) * 0.55 - text_size[0] / 2)
            ty = int(cy + (my - cy) * 0.55 + text_size[1] / 2)
            
            cv2.rectangle(frame, (tx - 4, ty - text_size[1] - 4),
                         (tx + text_size[0] + 4, ty + 6), (0, 0, 0), -1)
            cv2.rectangle(frame, (tx - 4, ty - text_size[1] - 4),
                         (tx + text_size[0] + 4, ty + 6), color, 1)
            
            text_color = state_colors.get(states[lane_num - 1], (255, 255, 255))
            cv2.putText(frame, text, (tx, ty),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1)
        
        # Crosshair
        cv2.line(frame, (cx - 12, cy), (cx + 12, cy), (255, 255, 255), 2)
        cv2.line(frame, (cx, cy - 12), (cx, cy + 12), (255, 255, 255), 2)
        
        # LOCKED indicator
        cv2.rectangle(frame, (5, 5), (130, 28), (0, 0, 0), -1)
        cv2.putText(frame, "LANES LOCKED", (10, 22),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        return frame

    @pyqtSlot()
    def lock_markers(self):
        """Manually lock current ArUco positions and start running."""
        if self._phase == "CALIBRATING" and len(self._locked_marker_positions) == 0:
            # Try to detect markers right now
            found_lanes = {}
            for marker_id, lane_num in self.aruco_lane_map.items():
                if marker_id in self.aruco_manager.marker_corners:
                    found_lanes[lane_num] = self.aruco_manager.marker_corners[marker_id].copy()
            
            found_bounds = {}
            for marker_id, b_type in self.aruco_boundary_map.items():
                if marker_id in self.aruco_manager.marker_corners:
                    found_bounds[b_type] = self.aruco_manager.marker_corners[marker_id].copy()
                    
            if len(found_lanes) >= 2:
                self._locked_marker_positions = found_lanes
                self._locked_boundary_positions = found_bounds
                all_pts = np.array(list(found_lanes.values()))
                self._locked_center = np.mean(all_pts, axis=0).astype(int)
                self._phase = "RUNNING"
                print(f"Manual lock: {len(found_lanes)} lanes and {len(found_bounds)} boundaries")
        elif self._phase == "CALIBRATING":
            self._phase = "RUNNING"
            print("Manual lock: using previously locked positions")

    @pyqtSlot()
    def unlock_markers(self):
        """Unlock markers - go back to calibrating without clearing positions."""
        self._phase = "CALIBRATING"
        self._count_history.clear()
        self._last_lane_counts = [0, 0, 0, 0]
        print("Markers unlocked - back to calibration mode")

    @pyqtSlot()
    def recalibrate(self):
        """Clear all locked data and restart calibration from scratch."""
        self._phase = "CALIBRATING"
        self._locked_marker_positions = {}
        self._locked_boundary_positions = {}
        self._locked_center = None
        self._count_history.clear()
        self._last_lane_counts = [0, 0, 0, 0]
        self._last_detections = None
        self._frame_count = 0
        self.traffic_controller = TrafficController()
        print("Recalibrating - all data cleared")

    @pyqtSlot()
    def stop(self):
        if self._poll_timer:
            self._poll_timer.stop()
        if self.camera:
            self.camera.stop()
        if self.esp32_bridge:
            self.esp32_bridge.disconnect()
        self.finished.emit()
