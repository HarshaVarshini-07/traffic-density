import cv2
import cv2.aruco as aruco
import numpy as np
import os

def analyze_image(image_path):
    if not os.path.exists(image_path):
        print(f"Error: File not found at {image_path}")
        return

    frame = cv2.imread(image_path)
    if frame is None:
        print("Error: Could not read image.")
        return

    print(f"Image Size: {frame.shape}")

    # Try common dictionaries
    dicts_to_test = [
        aruco.DICT_4X4_50,
        aruco.DICT_4X4_100,
        aruco.DICT_5X5_100,
        aruco.DICT_6X6_250,
        aruco.DICT_ARUCO_ORIGINAL
    ]
    
    dict_names = ["4x4_50", "4x4_100", "5x5_100", "6x6_250", "ORIGINAL"]

    found_markers = False

    for i, dictionary_id in enumerate(dicts_to_test):
        aruco_dict = aruco.getPredefinedDictionary(dictionary_id)
        parameters = aruco.DetectorParameters()
        detector = aruco.ArucoDetector(aruco_dict, parameters)

        corners, ids, rejected = detector.detectMarkers(frame)

        if ids is not None and len(ids) > 0:
            print(f"\nSUCCESS: Found {len(ids)} markers using dictionary: {dict_names[i]}")
            ids = ids.flatten()
            for j, marker_id in enumerate(ids):
                # Calculate center
                center = np.mean(corners[j][0], axis=0)
                print(f" - Marker ID {marker_id} at {center}")
            found_markers = True
            break # Assume one dictionary is used
    
    if not found_markers:
        print("\nNo markers found with common dictionaries. The image might be too blurry, lighting poor, or markers too small/occluded.")
        
        # Try converting to grayscale or enhancing contrast (optional)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Simple adaptive threshold usage is internal to detectMarkers, but we can double check
        # creating a basic loop for debugging if needed, but for now reporting failure is enough.

if __name__ == "__main__":
    analyze_image(r"C:\smarttraffic\prototype pic.jpeg")
