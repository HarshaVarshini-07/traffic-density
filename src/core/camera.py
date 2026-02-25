import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
import time

class CameraThread(QThread):
    """
    Dedicated thread for capturing video frames to ensure the GUI remains responsive.
    """
    frame_received = pyqtSignal(np.ndarray)
    
    def __init__(self, source=0):
        super().__init__()
        self.source = source
        self.running = True
        self.cap = None

    def run(self):
        self.cap = cv2.VideoCapture(self.source)
        
        # Optimize camera settings for speed if it's a webcam
        if isinstance(self.source, int):
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame_received.emit(frame)
            else:
                # If reading a file and it ends, loop or stop
                if isinstance(self.source, str):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Loop video
                else:
                    time.sleep(0.1) # Wait a bit if camera fails momentarily
                    
            # Limit header to ~60 FPS or just generic separate thread
            # self.msleep(10) 

        self.cap.release()

    def stop(self):
        self.running = False
        self.wait()
