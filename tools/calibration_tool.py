import cv2
import cv2.aruco as aruco
import numpy as np
import time

def calibration_tool(source=0):
    print(f"Starting Calibration Tool on Message Source: {source}")
    print("Press 'q' to quit.")
    
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Dictionary: 4x4_50 (detected in prototype)
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parameters = aruco.DetectorParameters()
    detector = aruco.ArucoDetector(aruco_dict, parameters)
    
    required_ids = {0, 1, 2, 3}
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break
            
        corners, ids, rejected = detector.detectMarkers(frame)
        
        detected_ids = set()
        if ids is not None:
            detected_ids = set(ids.flatten())
            aruco.drawDetectedMarkers(frame, corners, ids)
            
        # Draw Status Overlay
        # Draw a box for each required ID
        y_offset = 30
        for rid in sorted(required_ids):
            found = rid in detected_ids
            color = (0, 255, 0) if found else (0, 0, 255) # Green if found, Red if not
            text = f"Marker {rid}: {'FOUND' if found else 'MISSING'}"
            
            cv2.rectangle(frame, (10, y_offset - 25), (250, y_offset + 5), (0,0,0), -1)
            cv2.putText(frame, text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            y_offset += 40
            
        # Status Message
        if required_ids.issubset(detected_ids):
            msg = "READY FOR SYSTEM START"
            cv2.putText(frame, msg, (10, 700), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        else:
            msg = "ALIGN CAMERA / MARKERS"
            cv2.putText(frame, msg, (10, 700), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        cv2.imshow("Camera Calibration", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # If prototype image exists, we can test on it briefly (logic change, but here keeps to webcam)
    # calibration_tool(0)
    print("Run this script to check your camera feed.")
    calibration_tool()
