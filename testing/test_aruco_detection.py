"""
Test 4: ArUco Marker Detection
================================
Detects ArUco markers in the video frame.
If 4 markers are found, shows the perspective-warped top-down view.

Press 'q' to quit.
Press 'w' to toggle warp view.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'libs'))

import cv2
import numpy as np

VIDEO_SOURCE = 2  # Changed to live camera index (adjust if needed, e.g., 0, 1, 2)

# ArUco dictionary to use
ARUCO_DICT = cv2.aruco.DICT_ARUCO_MIP_36h12

def main():
    # Use DirectShow for faster initialization on Windows
    cap = cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_DSHOW)
    if not cap.isOpened():
        # Fallback to default backend
        cap = cv2.VideoCapture(VIDEO_SOURCE)
        if not cap.isOpened():
            print(f"ERROR: Cannot open camera source: {VIDEO_SOURCE}")
            return
            
    # Optimize camera settings
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Setup ArUco detector
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    aruco_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
    
    show_warp = False
    
    cv2.namedWindow("ArUco Detection Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ArUco Detection Test", 960, 720)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        display = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect markers
        corners, ids, rejected = detector.detectMarkers(gray)
        
        marker_count = 0
        marker_points = {}
        
        if ids is not None:
            marker_count = len(ids)
            # Draw detected markers
            cv2.aruco.drawDetectedMarkers(display, corners, ids)
            
            # Store marker centers by ID
            for i, marker_id in enumerate(ids.flatten()):
                c = corners[i][0]
                center = c.mean(axis=0).astype(int)
                marker_points[marker_id] = center
                
                # Draw center and ID
                cv2.circle(display, tuple(center), 8, (0, 0, 255), -1)
                cv2.putText(display, f"ID:{marker_id}", (center[0]+10, center[1]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Draw rejected candidates (dimmed)
        if rejected:
            for rej in rejected:
                pts = rej[0].astype(int)
                cv2.polylines(display, [pts], True, (100, 100, 100), 1)
        
        # Perspective warp if 4 markers found
        warped = None
        if len(marker_points) >= 4 and show_warp:
            try:
                # Sort marker IDs and get points in order (TL, TR, BR, BL)
                sorted_ids = sorted(marker_points.keys())[:4]
                src_pts = np.float32([marker_points[sid] for sid in sorted_ids])
                
                # Destination: 500x500 square
                dst_size = 500
                dst_pts = np.float32([[0, 0], [dst_size, 0], [dst_size, dst_size], [0, dst_size]])
                
                M = cv2.getPerspectiveTransform(src_pts, dst_pts)
                warped = cv2.warpPerspective(frame, M, (dst_size, dst_size))
            except Exception as e:
                print(f"Warp error: {e}")
        
        # Info bar
        info = np.zeros((60, display.shape[1], 3), dtype=np.uint8)
        info[:] = (30, 30, 30)
        status_color = (0, 255, 0) if marker_count >= 4 else (0, 200, 255) if marker_count > 0 else (0, 0, 255)
        cv2.putText(info, f"ArUco Markers Found: {marker_count}/4 | Dict: 4X4_50",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        cv2.putText(info, f"Press 'w' to toggle warp view | Press 'q' to quit",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        
        display = np.vstack([info, display])
        
        # Show warped view side by side
        if warped is not None:
            warped_resized = cv2.resize(warped, (display.shape[0], display.shape[0]))
            display = np.hstack([display, warped_resized])
        
        cv2.imshow("ArUco Detection Test", display)
        
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('w'):
            show_warp = not show_warp
            print(f"Warp view: {'ON' if show_warp else 'OFF'}")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
