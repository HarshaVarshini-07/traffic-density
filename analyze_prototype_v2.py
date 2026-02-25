import cv2
import cv2.aruco as aruco
import numpy as np

def analyze_image_aggressive(image_path):
    print(f"Analyzing: {image_path}")
    frame = cv2.imread(image_path)
    
    # Preprocessing: Try valid dictionary found earlier (4x4_50)
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parameters = aruco.DetectorParameters()
    
    # Aggressive parameters
    parameters.adaptiveThreshWinSizeMin = 3
    parameters.adaptiveThreshWinSizeMax = 23
    parameters.adaptiveThreshWinSizeStep = 10
    parameters.adaptiveThreshConstant = 7
    parameters.minMarkerPerimeterRate = 0.03 # Allow smaller markers
    parameters.polygonalApproxAccuracyRate = 0.05
    
    detector = aruco.ArucoDetector(aruco_dict, parameters)
    
    corners, ids, rejected = detector.detectMarkers(frame)
    
    print(f"Detections: {len(ids) if ids is not None else 0}")
    
    if ids is not None:
        ids = ids.flatten()
        for i, marker_id in enumerate(ids):
            center = np.mean(corners[i][0], axis=0)
            print(f"Found ID {marker_id} at {center}")
            
    # Also try to convert to grayscale and equalize histogram
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    corners_e, ids_e, _ = detector.detectMarkers(enhanced)
    if ids_e is not None:
         print(f"Enhanced Image Detections: {len(ids_e)}")
         for i, marker_id in enumerate(ids_e.flatten()):
             if ids is None or marker_id not in ids:
                 print(f"Found NEW ID {marker_id} in enhanced image")

if __name__ == "__main__":
    analyze_image_aggressive(r"C:\smarttraffic\prototype pic.jpeg")
