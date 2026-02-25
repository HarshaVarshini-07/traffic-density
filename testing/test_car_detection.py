"""
Test 1: Car/Vehicle Detection
=============================
Uses YOLOv8 via OpenCV DNN (ONNX format) to detect vehicles.
Falls back to basic color-based detection if ONNX model is not available.

Press 'q' to quit.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'libs'))

import cv2
import numpy as np

# --- Configuration ---
VIDEO_PATH = os.path.join(os.path.dirname(__file__), '..', 'Recording 2026-02-16 123437.mp4')
ONNX_MODEL = os.path.join(os.path.dirname(__file__), '..', 'yolov8n.onnx')
CONFIDENCE_THRESHOLD = 0.25

# COCO class names (relevant ones)
VEHICLE_CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
ALL_CLASSES = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}

def detect_with_onnx(frame, net, conf_threshold=0.25):
    """Run YOLOv8 ONNX model through OpenCV DNN."""
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
    net.setInput(blob)
    outputs = net.forward()
    
    # YOLOv8 output shape: [1, 84, 8400] -> transpose to [8400, 84]
    outputs = outputs[0].transpose()
    
    h, w = frame.shape[:2]
    boxes = []
    confidences = []
    class_ids = []
    
    for detection in outputs:
        scores = detection[4:]
        class_id = np.argmax(scores)
        confidence = scores[class_id]
        
        if confidence > conf_threshold and class_id in VEHICLE_CLASSES:
            cx, cy, bw, bh = detection[0], detection[1], detection[2], detection[3]
            
            # Scale to original image
            x1 = int((cx - bw/2) * w / 640)
            y1 = int((cy - bh/2) * h / 640)
            x2 = int((cx + bw/2) * w / 640)
            y2 = int((cy + bh/2) * h / 640)
            
            boxes.append([x1, y1, x2 - x1, y2 - y1])
            confidences.append(float(confidence))
            class_ids.append(class_id)
    
    # Non-maximum suppression
    if boxes:
        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, 0.45)
        results = []
        for i in indices:
            idx = i if isinstance(i, int) else i[0]
            results.append((boxes[idx], confidences[idx], class_ids[idx]))
        return results
    return []

def detect_with_color(frame):
    """Fallback: Simple color-based car detection (for toy cars)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    results = []
    
    # Blue car detection
    lower_blue = np.array([100, 80, 80])
    upper_blue = np.array([130, 255, 255])
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # Red car detection  
    lower_red1 = np.array([0, 80, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 80, 80])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
    
    # Yellow/Green car detection
    lower_yellow = np.array([20, 80, 80])
    upper_yellow = np.array([35, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    for mask, color_name in [(mask_blue, 'blue_car'), (mask_red, 'red_car'), (mask_yellow, 'yellow_car')]:
        # Clean up mask
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 500 < area < 50000:  # Filter by size
                x, y, w, h = cv2.boundingRect(cnt)
                results.append(([x, y, w, h], 0.8, color_name))
    
    return results

def main():
    print(f"Video: {VIDEO_PATH}")
    print(f"ONNX Model: {ONNX_MODEL}")
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video at {VIDEO_PATH}")
        return
    
    # Try ONNX model first
    use_onnx = False
    net = None
    if os.path.exists(ONNX_MODEL):
        try:
            net = cv2.dnn.readNetFromONNX(ONNX_MODEL)
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            use_onnx = True
            print("[OK] Using ONNX model for detection")
        except Exception as e:
            print(f"[WARN] ONNX failed: {e}. Using color detection.")
    else:
        print("[INFO] No ONNX model found. Using COLOR-BASED detection for toy cars.")
        print("       To use AI, export yolov8n to ONNX format.")
    
    cv2.namedWindow("Car Detection Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Car Detection Test", 960, 720)
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop
            continue
        
        frame_count += 1
        display = frame.copy()
        
        # Detect
        if use_onnx:
            detections = detect_with_onnx(frame, net, CONFIDENCE_THRESHOLD)
        else:
            detections = detect_with_color(frame)
        
        # Draw results
        car_count = 0
        for (box, conf, cls) in detections:
            x, y, w, h = box
            car_count += 1
            
            # Color based on class
            if isinstance(cls, str):
                label = cls
                color = (0, 255, 0)
            else:
                label = f"{VEHICLE_CLASSES.get(cls, 'vehicle')} {conf:.2f}"
                color = (0, 255, 0) if cls == 2 else (255, 165, 0)
            
            cv2.rectangle(display, (x, y), (x+w, y+h), color, 2)
            cv2.putText(display, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Info overlay
        method = "ONNX/YOLOv8" if use_onnx else "COLOR DETECTION"
        info_bg = np.zeros((80, display.shape[1], 3), dtype=np.uint8)
        info_bg[:] = (30, 30, 30)
        cv2.putText(info_bg, f"Method: {method} | Cars Detected: {car_count} | Frame: {frame_count}", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
        cv2.putText(info_bg, "Press 'q' to quit | Press 'c' to toggle Color/ONNX mode", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        
        display = np.vstack([info_bg, display])
        cv2.imshow("Car Detection Test", display)
        
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. Processed {frame_count} frames.")

if __name__ == "__main__":
    main()
