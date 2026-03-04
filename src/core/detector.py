try:
    from ultralytics import YOLO
    import supervision as sv
    import numpy as np
    import torch
    AI_AVAILABLE = True
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError as e:
    print(f"AI/Torch Import Error: {e}")
    AI_AVAILABLE = False
    CUDA_AVAILABLE = False
    # Mock classes for Safe Mode
    class YOLO: pass
    class sv: 
        class Detections:
            xyxy = None
            class_id = None
            tracker_id = None
            def from_ultralytics(self, res): return self

import json
import os

# Custom model classes (must match data.yaml)
CUSTOM_CLASSES = ['car', 'yellow_strip', 'black_strip', 'traffic_light', 'aruco_marker', 'boundary', 'mixed_lane', 'uno_breadboard', 'emergency_vehicle']


class VehicleDetector:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.3):
        self.ai_available = AI_AVAILABLE
        self.conf_threshold = conf_threshold
        self.is_custom_model = False
        self.device = "cpu"
        self._model_name = os.path.basename(model_path)
        self._num_classes = 0
        
        if self.ai_available:
            try:
                # Select best available device
                if CUDA_AVAILABLE:
                    self.device = "cuda"
                    print(f"CUDA GPU detected: {torch.cuda.get_device_name(0)}")
                else:
                    self.device = "cpu"
                    print("No CUDA GPU found, using CPU")
                
                self.model = YOLO(model_path)
                
                # Auto-detect custom model by checking class names
                model_names = self.model.names  # dict {0: 'car', 1: 'yellow_strip', ...}
                self._num_classes = len(model_names)
                
                if self._num_classes == len(CUSTOM_CLASSES) and model_names.get(0) == 'car':
                    self.is_custom_model = True
                    self.classes_to_detect = list(range(len(CUSTOM_CLASSES)))
                    self.classes_to_show = list(range(len(CUSTOM_CLASSES)))
                    self.class_names = CUSTOM_CLASSES
                    print(f"Custom {self._num_classes}-class model detected")
                else:
                    # COCO model: 2=car, 3=motorcycle, 5=bus, 7=truck
                    self.classes_to_detect = [2, 3, 5, 7]
                    self.classes_to_show = [2]
                    self.class_names = None  # Use model's built-in names
                    print(f"COCO model detected ({self._num_classes} classes)")
                
                self.tracker = sv.ByteTrack()
                self.box_annotator = sv.BoxAnnotator(thickness=2)
                self.label_annotator = sv.LabelAnnotator(text_scale=0.5, text_padding=5)
                print(f"Model loaded: {model_path} on {self.device.upper()}")
            except Exception as e:
                print(f"Model Load Error: {e}")
                self.ai_available = False
        
    @property
    def model_info(self):
        """Return model status info for GUI display."""
        if not self.ai_available:
            return {
                "model_type": "Not Loaded",
                "device": "N/A",
                "num_classes": 0,
                "model_name": "None"
            }
        return {
            "model_type": f"Custom {self._num_classes}-class" if self.is_custom_model else "COCO",
            "device": self.device.upper(),
            "num_classes": self._num_classes,
            "model_name": self._model_name
        }

    def detect(self, frame):
        """
        Detects objects using the loaded model.
        """
        if not self.ai_available:
            return sv.Detections.from_ultralytics(None)
            
        try:
            results = self.model(frame, verbose=False, conf=self.conf_threshold, device=self.device)[0]
            detections = sv.Detections.from_ultralytics(results)
            
            if not self.is_custom_model:
                # COCO model: filter to vehicles only
                detections = detections[np.isin(detections.class_id, self.classes_to_detect)]
            
            # Tracking
            detections = self.tracker.update_with_detections(detections)
            return detections
        except Exception as e:
            print(f"Detection Error: {e}")
            return sv.Detections.from_ultralytics(None)

    def get_car_detections(self, detections):
        """Extract only 'car' detections for lane counting."""
        if detections.class_id is None:
            return detections
        
        if self.is_custom_model:
            # Custom model: class 0 = car
            mask = detections.class_id == 0
        else:
            # COCO model: class 2 = car
            mask = np.isin(detections.class_id, self.classes_to_detect)
        
        return detections[mask]

    def get_emergency_detections(self, detections):
        """Extract emergency vehicle detections (custom model only, class 8)."""
        if not self.is_custom_model or detections.class_id is None:
            return None
        mask = detections.class_id == 8  # emergency_vehicle
        filtered = detections[mask]
        return filtered if len(filtered) > 0 else None

    def get_aruco_detections(self, detections):
        """Extract ArUco marker detections (custom model only, class 4)."""
        if not self.is_custom_model or detections.class_id is None:
            return None
        mask = detections.class_id == 4  # aruco_marker
        filtered = detections[mask]
        return filtered if len(filtered) > 0 else None

    def annotate(self, frame, detections, show_all=True):
        """
        Draws bounding boxes with labels.
        Only shows car (class 0) and emergency_vehicle (class 8) on screen.
        """
        if not self.ai_available or detections.class_id is None:
            return frame

        try:
            # Filter to only show cars and emergency vehicles on screen
            if self.is_custom_model:
                visible_mask = np.isin(detections.class_id, [0, 8])  # car, emergency_vehicle
                display_detections = detections[visible_mask]
            else:
                display_detections = detections
            
            if display_detections.class_id is None or len(display_detections.class_id) == 0:
                return frame
            
            # Annotate
            annotated_frame = self.box_annotator.annotate(scene=frame.copy(), detections=display_detections)
            
            # Labels
            labels = []
            if display_detections.tracker_id is not None:
                for class_id, tracker_id in zip(display_detections.class_id, display_detections.tracker_id):
                    if self.is_custom_model:
                        name = CUSTOM_CLASSES[class_id] if class_id < len(CUSTOM_CLASSES) else f"cls_{class_id}"
                    else:
                        name = self.model.names[class_id]
                    labels.append(f"{name} #{tracker_id}")
            elif display_detections.class_id is not None:
                for class_id in display_detections.class_id:
                    if self.is_custom_model:
                        name = CUSTOM_CLASSES[class_id] if class_id < len(CUSTOM_CLASSES) else f"cls_{class_id}"
                    else:
                        name = self.model.names[class_id]
                    labels.append(name)
            
            annotated_frame = self.label_annotator.annotate(
                scene=annotated_frame, detections=display_detections, labels=labels
            )
            
            return annotated_frame
        except Exception as e:
            print(f"Annotation Error: {e}")
            return frame
