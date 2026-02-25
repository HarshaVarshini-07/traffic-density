"""
Smart Traffic - Live Detection from Training Data
===================================================
Uses the labeled training data to detect objects on a live camera feed.
Since torch/YOLO is unavailable, this uses OpenCV-based methods:
- Extracts color profiles from labeled regions
- Uses template matching + color segmentation for detection
- Shows live detections with bounding boxes

Usage:
    python tools/live_detect_from_training.py
"""
import cv2
import numpy as np
import os
import glob
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
IMAGES_DIR = os.path.join(PROJECT_ROOT, 'tools', 'training_data', 'images')
LABELS_DIR = os.path.join(PROJECT_ROOT, 'tools', 'training_data', 'labels')
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'config.json')

CLASSES = ['car', 'yellow_strip', 'black_strip', 'traffic_light', 'aruco_marker', 'boundary']
COLORS_BGR = {
    0: (100, 255, 0),     # car
    1: (0, 255, 255),     # yellow_strip 
    2: (128, 128, 128),   # black_strip
    3: (100, 100, 255),   # traffic_light
    4: (255, 200, 100),   # aruco_marker
    5: (255, 100, 200),   # boundary
}


def load_training_data():
    """Load all labeled training data and extract color profiles for each class."""
    print("Loading training data...")
    
    # Collect HSV color samples per class
    class_hsv_samples = {i: [] for i in range(len(CLASSES))}
    # Collect template patches for template matching
    class_templates = {i: [] for i in range(len(CLASSES))}
    
    images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.jpg")))
    
    for img_path in images:
        filename = os.path.basename(img_path)
        label_path = os.path.join(LABELS_DIR, filename.replace('.jpg', '.txt'))
        
        if not os.path.exists(label_path):
            continue
        
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        h, w = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                
                cls_id = int(parts[0])
                
                if len(parts) == 5:
                    # Bounding box
                    cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    x1 = max(0, int((cx - bw/2) * w))
                    y1 = max(0, int((cy - bh/2) * h))
                    x2 = min(w, int((cx + bw/2) * w))
                    y2 = min(h, int((cy + bh/2) * h))
                    
                    if x2 > x1 and y2 > y1:
                        roi_hsv = hsv[y1:y2, x1:x2]
                        roi_bgr = img[y1:y2, x1:x2]
                        if roi_hsv.size > 0:
                            class_hsv_samples[cls_id].append(roi_hsv.reshape(-1, 3))
                            # Store small template
                            if roi_bgr.shape[0] > 0 and roi_bgr.shape[1] > 0:
                                template = cv2.resize(roi_bgr, (64, 64))
                                class_templates[cls_id].append(template)
                else:
                    # Polygon - create mask and extract pixels
                    coords = [float(v) for v in parts[1:]]
                    points = []
                    for i in range(0, len(coords) - 1, 2):
                        px = int(coords[i] * w)
                        py = int(coords[i+1] * h)
                        points.append([px, py])
                    
                    if len(points) >= 3:
                        pts = np.array(points, np.int32)
                        mask = np.zeros((h, w), dtype=np.uint8)
                        cv2.fillPoly(mask, [pts], 255)
                        
                        # Extract HSV pixels inside polygon
                        pixels = hsv[mask > 0]
                        if len(pixels) > 0:
                            class_hsv_samples[cls_id].append(pixels)
                        
                        # Template from bounding rect
                        x, y, rw, rh = cv2.boundingRect(pts)
                        # Clamp to image bounds
                        x = max(0, x)
                        y = max(0, y)
                        rw = min(rw, w - x)
                        rh = min(rh, h - y)
                        if rw > 5 and rh > 5:
                            roi = img[y:y+rh, x:x+rw]
                            if roi.size > 0 and roi.shape[0] > 0 and roi.shape[1] > 0:
                                template = cv2.resize(roi, (64, 64))
                                class_templates[cls_id].append(template)
    
    # Compute HSV ranges for each class
    class_hsv_ranges = {}
    for cls_id, samples in class_hsv_samples.items():
        if samples:
            all_pixels = np.vstack(samples)
            # Use percentile-based ranges for robustness
            lower = np.percentile(all_pixels, 10, axis=0).astype(np.uint8)
            upper = np.percentile(all_pixels, 90, axis=0).astype(np.uint8)
            
            # Widen ranges slightly for tolerance
            lower = np.maximum(lower.astype(int) - 15, 0).astype(np.uint8)
            upper = np.minimum(upper.astype(int) + 15, [179, 255, 255]).astype(np.uint8)
            
            class_hsv_ranges[cls_id] = (lower, upper)
            print(f"  {CLASSES[cls_id]}: HSV range [{lower}] to [{upper}] ({len(all_pixels)} pixels)")
    
    print(f"Loaded {len(images)} images, {sum(len(v) for v in class_templates.values())} templates")
    return class_hsv_ranges, class_templates


def detect_by_color(frame, hsv_ranges):
    """Detect objects using color segmentation based on learned HSV ranges."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]
    detections = []
    
    for cls_id, (lower, upper) in hsv_ranges.items():
        # Handle hue wraparound
        if lower[0] > upper[0]:
            mask1 = cv2.inRange(hsv, lower, np.array([179, upper[1], upper[2]], dtype=np.uint8))
            mask2 = cv2.inRange(hsv, np.array([0, lower[1], lower[2]], dtype=np.uint8), upper)
            mask = mask1 | mask2
        else:
            mask = cv2.inRange(hsv, lower, upper)
        
        # Clean up mask
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 200:  # Min area filter
                continue
            
            x, y, cw, ch = cv2.boundingRect(cnt)
            
            # Check if it's a polygon-like shape or rectangle-like
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            
            detections.append({
                'class_id': cls_id,
                'class_name': CLASSES[cls_id],
                'bbox': (x, y, cw, ch),
                'contour': cnt,
                'area': area,
                'confidence': min(1.0, area / 1000),  # Rough confidence
                'solidity': solidity
            })
    
    return detections


def draw_detections(frame, detections):
    """Draw all detections on frame."""
    display = frame.copy()
    
    for det in detections:
        cls_id = det['class_id']
        color = COLORS_BGR.get(cls_id, (0, 255, 0))
        x, y, w, h = det['bbox']
        
        # Draw contour with fill
        overlay = display.copy()
        cv2.drawContours(overlay, [det['contour']], -1, color, -1)
        cv2.addWeighted(overlay, 0.25, display, 0.75, 0, display)
        
        # Draw outline
        cv2.drawContours(display, [det['contour']], -1, color, 2)
        
        # Label
        label = f"{det['class_name']}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(display, (x, y-20), (x+lw+4, y), color, -1)
        cv2.putText(display, label, (x+2, y-5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    return display


def main():
    # Load training data
    hsv_ranges, templates = load_training_data()
    
    if not hsv_ranges:
        print("ERROR: No training data found! Label some images first.")
        return
    
    # Open camera
    cam_source = 2  # Default
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
    
    print("Live detection running! Press Q to quit.")
    print("Detection classes:", [CLASSES[c] for c in hsv_ranges.keys()])
    
    fps_timer = cv2.getTickCount()
    frame_count = 0
    fps = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Detect
        detections = detect_by_color(frame, hsv_ranges)
        
        # Draw
        display = draw_detections(frame, detections)
        
        # FPS counter
        frame_count += 1
        if frame_count >= 10:
            elapsed = (cv2.getTickCount() - fps_timer) / cv2.getTickFrequency()
            fps = frame_count / elapsed
            fps_timer = cv2.getTickCount()
            frame_count = 0
        
        # Info bar
        h, w = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w, 40), (30, 30, 30), -1)
        
        # Count by class
        counts = {}
        for d in detections:
            counts[d['class_name']] = counts.get(d['class_name'], 0) + 1
        
        info = f"FPS: {fps:.0f} | Detections: {len(detections)}"
        if counts:
            info += " | " + " ".join([f"{k}:{v}" for k, v in counts.items()])
        
        cv2.putText(display, info, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 200), 2)
        
        # Legend
        y_offset = 55
        for cls_id in hsv_ranges:
            color = COLORS_BGR[cls_id]
            cv2.rectangle(display, (w-180, y_offset-12), (w-165, y_offset+2), color, -1)
            cv2.putText(display, CLASSES[cls_id], (w-160, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            y_offset += 20
        
        cv2.imshow("Smart Traffic - Live Detection", display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print("Detection stopped.")


if __name__ == "__main__":
    main()
