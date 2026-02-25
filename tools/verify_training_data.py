"""
Verify Training Data - Displays annotations overlaid on images.
Press LEFT/RIGHT arrows to navigate, Q to quit.
"""
import cv2
import numpy as np
import os
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
IMAGES_DIR = os.path.join(PROJECT_ROOT, 'tools', 'training_data', 'images')
LABELS_DIR = os.path.join(PROJECT_ROOT, 'tools', 'training_data', 'labels')

CLASSES = ['car', 'yellow_strip', 'black_strip', 'traffic_light', 'aruco_marker', 'boundary']
COLORS = {
    0: (100, 255, 0),     # car - green
    1: (0, 255, 255),     # yellow_strip - yellow
    2: (128, 128, 128),   # black_strip - gray
    3: (100, 100, 255),   # traffic_light - red
    4: (255, 200, 100),   # aruco_marker - light blue
    5: (255, 100, 200),   # boundary - purple
}

def draw_annotations(img, label_path):
    """Draw all annotations on an image."""
    h, w = img.shape[:2]
    display = img.copy()
    count_by_class = {}
    
    if not os.path.exists(label_path):
        cv2.putText(display, "NO LABELS", (w//2 - 80, h//2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        return display, count_by_class
    
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            
            cls_id = int(parts[0])
            cls_name = CLASSES[cls_id] if cls_id < len(CLASSES) else f"cls_{cls_id}"
            color = COLORS.get(cls_id, (0, 255, 0))
            count_by_class[cls_name] = count_by_class.get(cls_name, 0) + 1
            
            if len(parts) == 5:
                # Rectangle: cls cx cy bw bh
                cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                x1 = int((cx - bw/2) * w)
                y1 = int((cy - bh/2) * h)
                x2 = int((cx + bw/2) * w)
                y2 = int((cy + bh/2) * h)
                
                cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                # Label
                label = f"{cls_name}"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(display, (x1, y1-20), (x1+lw+4, y1), color, -1)
                cv2.putText(display, label, (x1+2, y1-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            else:
                # Polygon: cls x1 y1 x2 y2 ... xN yN
                coords = [float(v) for v in parts[1:]]
                points = []
                for i in range(0, len(coords) - 1, 2):
                    px = int(coords[i] * w)
                    py = int(coords[i+1] * h)
                    points.append([px, py])
                
                if len(points) >= 3:
                    pts = np.array(points, np.int32).reshape((-1, 1, 2))
                    # Semi-transparent fill
                    overlay = display.copy()
                    cv2.fillPoly(overlay, [pts], color)
                    cv2.addWeighted(overlay, 0.3, display, 0.7, 0, display)
                    # Outline
                    cv2.polylines(display, [pts], True, color, 2)
                    # Label at first point
                    label = f"{cls_name} (poly)"
                    (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(display, (points[0][0], points[0][1]-20), 
                                 (points[0][0]+lw+4, points[0][1]), color, -1)
                    cv2.putText(display, label, (points[0][0]+2, points[0][1]-5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    return display, count_by_class


def main():
    images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.jpg")))
    if not images:
        print("No images found!")
        return
    
    idx = 0
    total = len(images)
    print(f"Found {total} images. Use LEFT/RIGHT arrows to navigate, Q to quit.")
    
    while True:
        img_path = images[idx]
        filename = os.path.basename(img_path)
        label_path = os.path.join(LABELS_DIR, filename.replace('.jpg', '.txt'))
        
        img = cv2.imread(img_path)
        if img is None:
            idx = (idx + 1) % total
            continue
        
        display, counts = draw_annotations(img, label_path)
        
        # Header bar
        h, w = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w, 35), (30, 30, 30), -1)
        header = f"[{idx+1}/{total}] {filename}"
        cv2.putText(display, header, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 200), 2)
        
        # Stats bar
        if counts:
            stats = " | ".join([f"{k}: {v}" for k, v in counts.items()])
        else:
            stats = "No annotations"
        cv2.rectangle(display, (0, h-30), (w, h), (30, 30, 30), -1)
        cv2.putText(display, stats, (10, h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        
        # Controls hint
        cv2.putText(display, "LEFT/RIGHT: navigate | Q: quit", (w-350, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        
        cv2.imshow("Training Data Verification", display)
        
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            break
        elif key == 83 or key == ord('d'):  # RIGHT arrow or D
            idx = (idx + 1) % total
        elif key == 81 or key == ord('a'):  # LEFT arrow or A
            idx = (idx - 1) % total
    
    cv2.destroyAllWindows()
    print("Verification complete.")


if __name__ == "__main__":
    main()
