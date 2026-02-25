"""
Test 2: Lane Detection & Assignment
====================================
Divides the frame into 4 lanes (quadrants) and assigns detected cars to lanes.
Uses color-based detection for toy cars.

Press 'q' to quit.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'libs'))

import cv2
import numpy as np

VIDEO_PATH = os.path.join(os.path.dirname(__file__), '..', 'Recording 2026-02-16 123437.mp4')

# Lane colors
LANE_COLORS = [
    (0, 200, 255),   # Lane 1 (Top-Left) - Orange
    (0, 255, 0),     # Lane 2 (Top-Right) - Green
    (255, 100, 100), # Lane 3 (Bottom-Right) - Blue
    (200, 0, 255),   # Lane 4 (Bottom-Left) - Pink
]
LANE_NAMES = ["Lane 1 (TL)", "Lane 2 (TR)", "Lane 3 (BR)", "Lane 4 (BL)"]

def detect_cars_color(frame):
    """Simple color-based toy car detection."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    results = []
    
    # Blue cars
    mask = cv2.inRange(hsv, np.array([100, 80, 80]), np.array([130, 255, 255]))
    # Red cars
    mask_r1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
    mask_r2 = cv2.inRange(hsv, np.array([170, 80, 80]), np.array([180, 255, 255]))
    mask = mask | mask_r1 | mask_r2
    # Yellow cars
    mask_y = cv2.inRange(hsv, np.array([20, 80, 80]), np.array([35, 255, 255]))
    mask = mask | mask_y
    
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 500 < area < 50000:
            x, y, w, h = cv2.boundingRect(cnt)
            cx = x + w // 2
            cy = y + h // 2
            results.append((x, y, w, h, cx, cy))
    
    return results

def assign_lane(cx, cy, frame_w, frame_h):
    """Assign a detection to a lane based on quadrant."""
    mid_x = frame_w // 2
    mid_y = frame_h // 2
    
    if cx < mid_x and cy < mid_y:
        return 0  # Lane 1 (Top-Left)
    elif cx >= mid_x and cy < mid_y:
        return 1  # Lane 2 (Top-Right)
    elif cx >= mid_x and cy >= mid_y:
        return 2  # Lane 3 (Bottom-Right)
    else:
        return 3  # Lane 4 (Bottom-Left)

def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {VIDEO_PATH}")
        return
    
    cv2.namedWindow("Lane Detection Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Lane Detection Test", 960, 720)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        h, w = frame.shape[:2]
        display = frame.copy()
        mid_x, mid_y = w // 2, h // 2
        
        # Draw lane boundaries
        cv2.line(display, (mid_x, 0), (mid_x, h), (255, 255, 255), 2)
        cv2.line(display, (0, mid_y), (w, mid_y), (255, 255, 255), 2)
        
        # Lane labels
        for i, name in enumerate(LANE_NAMES):
            if i == 0: pos = (10, 30)
            elif i == 1: pos = (mid_x + 10, 30)
            elif i == 2: pos = (mid_x + 10, mid_y + 30)
            else: pos = (10, mid_y + 30)
            cv2.putText(display, name, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, LANE_COLORS[i], 2)
        
        # Tint each quadrant
        overlay = display.copy()
        alpha = 0.15
        for i in range(4):
            if i == 0: cv2.rectangle(overlay, (0, 0), (mid_x, mid_y), LANE_COLORS[i], -1)
            elif i == 1: cv2.rectangle(overlay, (mid_x, 0), (w, mid_y), LANE_COLORS[i], -1)
            elif i == 2: cv2.rectangle(overlay, (mid_x, mid_y), (w, h), LANE_COLORS[i], -1)
            else: cv2.rectangle(overlay, (0, mid_y), (mid_x, h), LANE_COLORS[i], -1)
        cv2.addWeighted(overlay, alpha, display, 1 - alpha, 0, display)
        
        # Detect and assign
        detections = detect_cars_color(frame)
        lane_counts = [0, 0, 0, 0]
        
        for (x, y, bw, bh, cx, cy) in detections:
            lane = assign_lane(cx, cy, w, h)
            lane_counts[lane] += 1
            color = LANE_COLORS[lane]
            
            cv2.rectangle(display, (x, y), (x+bw, y+bh), color, 2)
            cv2.circle(display, (cx, cy), 5, color, -1)
            cv2.putText(display, f"L{lane+1}", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Stats bar
        stats = np.zeros((60, w, 3), dtype=np.uint8)
        stats[:] = (30, 30, 30)
        for i in range(4):
            text = f"{LANE_NAMES[i]}: {lane_counts[i]} cars"
            x_pos = i * (w // 4) + 10
            cv2.putText(stats, text, (x_pos, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, LANE_COLORS[i], 1)
        
        display = np.vstack([stats, display])
        cv2.imshow("Lane Detection Test", display)
        
        if cv2.waitKey(30) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
