"""
Smart Traffic - Test Trained Model on Live Camera
===================================================
Loads the custom-trained YOLO model and runs detection on live camera feed.

Usage:
    python test_trained_model.py
"""
import sys
import os

# Use local libs for torch/ultralytics
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libs'))

import cv2
import json
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                          'runs', 'detect', 'runs', 'detect', 'smart_traffic', 'weights', 'best.pt')
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

CLASSES = ['car', 'yellow_strip', 'black_strip', 'traffic_light', 'aruco_marker', 'boundary', 'mixed_lane', 'uno_breadboard']
COLORS = [
    (100, 255, 0),     # car - green
    (0, 255, 255),     # yellow_strip - yellow
    (128, 128, 128),   # black_strip - gray
    (100, 100, 255),   # traffic_light - red
    (255, 200, 100),   # aruco_marker - light blue
    (255, 100, 200),   # boundary - purple
    (0, 165, 255),     # mixed_lane - orange
    (200, 200, 0),     # uno_breadboard - cyan
]


def main():
    from ultralytics import YOLO
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}")
        return
    
    print(f"Loading model: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    print("Model loaded!")
    
    # Get camera source
    cam_source = 2
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                src = cfg.get("camera_source", "2")
                cam_source = int(src) if src.isdigit() else src
        except:
            pass
    
    print(f"Opening camera {cam_source}...")
    cap = cv2.VideoCapture(cam_source)
    if not cap.isOpened():
        print(f"ERROR: Cannot open camera {cam_source}")
        return
    
    print("=" * 50)
    print("Live Detection Running!")
    print("Press Q to quit")
    print("Press +/- to adjust confidence threshold")
    print("=" * 50)
    
    conf_threshold = 0.3
    fps_timer = cv2.getTickCount()
    frame_count = 0
    fps = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Run YOLO inference
        results = model(frame, conf=conf_threshold, verbose=False)
        
        display = frame.copy()
        detections_by_class = {}
        
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    cls_name = CLASSES[cls_id] if cls_id < len(CLASSES) else f"cls_{cls_id}"
                    color = COLORS[cls_id] if cls_id < len(COLORS) else (0, 255, 0)
                    
                    # Count detections
                    detections_by_class[cls_name] = detections_by_class.get(cls_name, 0) + 1
                    
                    # Draw box
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    
                    # Semi-transparent fill
                    overlay = display.copy()
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                    cv2.addWeighted(overlay, 0.15, display, 0.85, 0, display)
                    
                    # Label with confidence
                    label = f"{cls_name} {conf:.0%}"
                    (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(display, (x1, y1 - 22), (x1 + lw + 4, y1), color, -1)
                    cv2.putText(display, label, (x1 + 2, y1 - 6),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # FPS
        frame_count += 1
        if frame_count >= 10:
            elapsed = (cv2.getTickCount() - fps_timer) / cv2.getTickFrequency()
            fps = frame_count / elapsed
            fps_timer = cv2.getTickCount()
            frame_count = 0
        
        # Info bar at top
        h, w = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w, 45), (20, 20, 20), -1)
        
        total_det = sum(detections_by_class.values())
        info = f"FPS: {fps:.0f} | Conf: {conf_threshold:.0%} | Detections: {total_det}"
        cv2.putText(display, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 200), 2)
        
        # Class counts at bottom
        if detections_by_class:
            cv2.rectangle(display, (0, h - 35), (w, h), (20, 20, 20), -1)
            counts_text = " | ".join([f"{k}: {v}" for k, v in detections_by_class.items()])
            cv2.putText(display, counts_text, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        
        # Legend on right
        y_off = 60
        for i, cls_name in enumerate(CLASSES):
            color = COLORS[i]
            cv2.rectangle(display, (w - 180, y_off - 12), (w - 165, y_off + 2), color, -1)
            count = detections_by_class.get(cls_name, 0)
            label = f"{cls_name} ({count})" if count > 0 else cls_name
            text_color = (255, 255, 255) if count > 0 else (100, 100, 100)
            cv2.putText(display, label, (w - 160, y_off),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, 1)
            y_off += 22
        
        cv2.imshow("Smart Traffic - YOLO Detection", display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('+') or key == ord('='):
            conf_threshold = min(0.95, conf_threshold + 0.05)
            print(f"Confidence: {conf_threshold:.0%}")
        elif key == ord('-'):
            conf_threshold = max(0.05, conf_threshold - 0.05)
            print(f"Confidence: {conf_threshold:.0%}")
    
    cap.release()
    cv2.destroyAllWindows()
    print("Detection stopped.")


if __name__ == "__main__":
    main()
