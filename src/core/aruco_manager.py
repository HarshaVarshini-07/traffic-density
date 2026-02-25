import cv2
import numpy as np

class ArucoManager:
    def __init__(self, marker_dict=cv2.aruco.DICT_4X4_50, marker_length=0.05):
        self.dictionary = cv2.aruco.getPredefinedDictionary(marker_dict)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.dictionary, self.parameters)
        
        self.marker_corners = {}
        self.homography_matrix = None
        self.warped_size = (640, 640) # Target size for top-down view

    def detect_markers(self, frame):
        """
        Detects ArUco markers and updates internal state.
        Expects 4 markers to define the ground plane.
        """
        corners, ids, rejected = self.detector.detectMarkers(frame)
        
        if ids is not None:
            ids = ids.flatten()
            for i, marker_id in enumerate(ids):
                # Store the center of the marker
                marker_center = np.mean(corners[i][0], axis=0)
                self.marker_corners[marker_id] = marker_center
                
        # If we have 4 markers, we can calculate homography
        if len(self.marker_corners) >= 4:
            self._calculate_homography()
            return True
        return False

    def _calculate_homography(self):
        """
        Calculates the homography matrix based on 4 markers.
        Assumes ids 0, 1, 2, 3 correspond to Top-Left, Top-Right, Bottom-Right, Bottom-Left
        (or just sorts them by position).
        """
        points = list(self.marker_corners.values())
        
        # Sort points to ensure consistent order: TL, TR, BR, BL
        # Sort by Y first (Top vs Bottom)
        points = sorted(points, key=lambda x: x[1])
        # Top two
        top = sorted(points[:2], key=lambda x: x[0])
        # Bottom two
        bottom = sorted(points[2:], key=lambda x: x[0])
        
        sorted_points = np.array([top[0], top[1], bottom[1], bottom[0]], dtype=np.float32)
        
        # Destination points (Top-Down View)
        w, h = self.warped_size
        dst_points = np.array([
            [0, 0],
            [w, 0],
            [w, h],
            [0, h]
        ], dtype=np.float32)
        
        self.homography_matrix = cv2.getPerspectiveTransform(sorted_points, dst_points)

    def warp(self, frame):
        """
        Warps the frame to top-down view if homography is available.
        """
        if self.homography_matrix is not None:
            return cv2.warpPerspective(frame, self.homography_matrix, self.warped_size)
        return frame

    def draw_markers(self, frame):
        """
        Draws detected markers on the frame for debugging.
        """
        # Re-detect for visualization (or store corners)
        corners, ids, _ = self.detector.detectMarkers(frame)
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        return frame
