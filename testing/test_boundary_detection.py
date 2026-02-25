"""
Test 5: Boundary / Road Edge Detection
========================================
Detects road boundaries using edge detection and contour analysis.
Highlights the road area vs non-road area.

Press 'q' to quit.
Press 'm' to cycle through detection modes.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'libs'))

import cv2
import numpy as np

VIDEO_PATH = os.path.join(os.path.dirname(__file__), '..', 'Recording 2026-02-16 123437.mp4')

MODES = ["Canny Edges", "Road Mask (Dark Surface)", "Yellow Lines", "All Combined"]

def detect_edges(frame):
    """Canny edge detection for road boundaries."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    # Dilate edges for visibility
    kernel = np.ones((2, 2), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    return edges

def detect_road_surface(frame):
    """Detect dark road surface (black roads in the model)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Dark surfaces (roads are usually dark/black)
    lower_dark = np.array([0, 0, 0])
    upper_dark = np.array([180, 100, 80])
    mask = cv2.inRange(hsv, lower_dark, upper_dark)
    
    # Clean up
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    return mask

def detect_yellow_lines(frame):
    """Detect yellow/black strip lane markings."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Yellow color range
    lower_yellow = np.array([15, 80, 80])
    upper_yellow = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    return mask

def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {VIDEO_PATH}")
        return
    
    mode = 0
    cv2.namedWindow("Boundary Detection Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Boundary Detection Test", 960, 720)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        display = frame.copy()
        h, w = frame.shape[:2]
        
        if mode == 0:  # Canny Edges
            edges = detect_edges(frame)
            edge_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            edge_colored[:, :, 0] = 0  # Remove blue channel
            edge_colored[:, :, 2] = 0  # Remove red channel -> green edges
            display = cv2.addWeighted(display, 0.7, edge_colored, 1.0, 0)
            
        elif mode == 1:  # Road Surface
            road_mask = detect_road_surface(frame)
            overlay = display.copy()
            overlay[road_mask > 0] = [50, 50, 200]  # Highlight road in red tint
            display = cv2.addWeighted(overlay, 0.4, display, 0.6, 0)
            
            # Draw contours
            contours, _ = cv2.findContours(road_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(display, contours, -1, (0, 255, 0), 2)
            
        elif mode == 2:  # Yellow Lines
            yellow_mask = detect_yellow_lines(frame)
            overlay = display.copy()
            overlay[yellow_mask > 0] = [0, 255, 255]  # Yellow highlight
            display = cv2.addWeighted(overlay, 0.6, display, 0.4, 0)
            
        elif mode == 3:  # All Combined
            edges = detect_edges(frame)
            road_mask = detect_road_surface(frame)
            yellow_mask = detect_yellow_lines(frame)
            
            overlay = display.copy()
            overlay[road_mask > 0] = [80, 50, 50]   # Road: dark blue tint
            overlay[yellow_mask > 0] = [0, 255, 255] # Yellow lines
            display = cv2.addWeighted(overlay, 0.4, display, 0.6, 0)
            
            edge_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            edge_colored[:, :, 0] = 0
            edge_colored[:, :, 2] = 0
            display = cv2.addWeighted(display, 0.8, edge_colored, 0.5, 0)
        
        # Info bar
        info = np.zeros((60, w, 3), dtype=np.uint8)
        info[:] = (30, 30, 30)
        cv2.putText(info, f"Mode: {MODES[mode]}", (10, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
        cv2.putText(info, "Press 'm' to change mode | Press 'q' to quit",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        
        display = np.vstack([info, display])
        cv2.imshow("Boundary Detection Test", display)
        
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('m'):
            mode = (mode + 1) % len(MODES)
            print(f"Switched to mode: {MODES[mode]}")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
