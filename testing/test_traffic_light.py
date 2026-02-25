"""
Test 3: Traffic Light Simulation
=================================
Simulates traffic light states based on lane density.
The lane with the most cars gets green first.

Press 'q' to quit.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'libs'))

import cv2
import numpy as np
import time

VIDEO_PATH = os.path.join(os.path.dirname(__file__), '..', 'Recording 2026-02-16 123437.mp4')

# Traffic light state machine
class TrafficLightSim:
    def __init__(self):
        self.states = ['R', 'R', 'R', 'R']  # R=Red, Y=Yellow, G=Green
        self.active_lane = 0
        self.last_switch = time.time()
        self.green_time = 5.0   # seconds
        self.yellow_time = 2.0
        self.phase = 'GREEN'  # GREEN or YELLOW
    
    def update(self, lane_counts):
        now = time.time()
        elapsed = now - self.last_switch
        
        if self.phase == 'GREEN' and elapsed > self.green_time:
            # Switch to yellow
            self.states[self.active_lane] = 'Y'
            self.phase = 'YELLOW'
            self.last_switch = now
        
        elif self.phase == 'YELLOW' and elapsed > self.yellow_time:
            # Switch to red, find next busiest lane
            self.states[self.active_lane] = 'R'
            
            # Pick the lane with highest density (excluding current)
            max_count = -1
            next_lane = (self.active_lane + 1) % 4
            for i in range(4):
                if i != self.active_lane and lane_counts[i] > max_count:
                    max_count = lane_counts[i]
                    next_lane = i
            
            self.active_lane = next_lane
            self.states[self.active_lane] = 'G'
            self.phase = 'GREEN'
            self.last_switch = now
        
        elif self.phase == 'GREEN':
            self.states[self.active_lane] = 'G'
        
        return self.states.copy(), self.active_lane, self.phase, elapsed

def detect_cars_color(frame):
    """Simple color-based toy car detection."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([100, 80, 80]), np.array([130, 255, 255]))
    mask_r1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
    mask_r2 = cv2.inRange(hsv, np.array([170, 80, 80]), np.array([180, 255, 255]))
    mask_y = cv2.inRange(hsv, np.array([20, 80, 80]), np.array([35, 255, 255]))
    mask = mask | mask_r1 | mask_r2 | mask_y
    
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    for cnt in contours:
        if 500 < cv2.contourArea(cnt) < 50000:
            x, y, w, h = cv2.boundingRect(cnt)
            results.append((x + w//2, y + h//2))
    return results

def draw_traffic_light(display, lane_id, state, x, y):
    """Draw a mini traffic light at position (x,y)."""
    colors = {
        'R': ((0, 0, 200), (50, 50, 50), (50, 50, 50)),
        'Y': ((50, 50, 50), (0, 200, 255), (50, 50, 50)),
        'G': ((50, 50, 50), (50, 50, 50), (0, 200, 0)),
    }
    r, y_c, g = colors.get(state, colors['R'])
    
    # Background
    cv2.rectangle(display, (x-15, y-45), (x+15, y+45), (20, 20, 20), -1)
    cv2.rectangle(display, (x-15, y-45), (x+15, y+45), (100, 100, 100), 2)
    
    # Lights
    cv2.circle(display, (x, y-25), 10, r, -1)
    cv2.circle(display, (x, y), 10, y_c, -1)
    cv2.circle(display, (x, y+25), 10, g, -1)
    
    # Label
    cv2.putText(display, f"L{lane_id+1}", (x-10, y+65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {VIDEO_PATH}")
        return
    
    sim = TrafficLightSim()
    cv2.namedWindow("Traffic Light Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Traffic Light Test", 960, 720)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        h, w = frame.shape[:2]
        display = frame.copy()
        mid_x, mid_y = w // 2, h // 2
        
        # Detect and count per lane
        cars = detect_cars_color(frame)
        lane_counts = [0, 0, 0, 0]
        for cx, cy in cars:
            if cx < mid_x and cy < mid_y: lane_counts[0] += 1
            elif cx >= mid_x and cy < mid_y: lane_counts[1] += 1
            elif cx >= mid_x and cy >= mid_y: lane_counts[2] += 1
            else: lane_counts[3] += 1
        
        # Update traffic lights
        states, active, phase, elapsed = sim.update(lane_counts)
        
        # Draw lane boundaries
        cv2.line(display, (mid_x, 0), (mid_x, h), (100, 100, 100), 1)
        cv2.line(display, (0, mid_y), (w, mid_y), (100, 100, 100), 1)
        
        # Draw traffic lights at lane centers
        positions = [
            (mid_x // 2, mid_y // 2),       # Lane 1 center
            (mid_x + mid_x // 2, mid_y // 2), # Lane 2 center
            (mid_x + mid_x // 2, mid_y + mid_y // 2), # Lane 3 center
            (mid_x // 2, mid_y + mid_y // 2), # Lane 4 center
        ]
        for i in range(4):
            draw_traffic_light(display, i, states[i], positions[i][0], positions[i][1])
        
        # Info bar
        info = np.zeros((80, w, 3), dtype=np.uint8)
        info[:] = (30, 30, 30)
        state_text = " | ".join([f"L{i+1}: {states[i]} ({lane_counts[i]})" for i in range(4)])
        cv2.putText(info, state_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2)
        cv2.putText(info, f"Active: Lane {active+1} | Phase: {phase} | Timer: {elapsed:.1f}s", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        
        display = np.vstack([info, display])
        cv2.imshow("Traffic Light Test", display)
        
        if cv2.waitKey(30) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
