import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex
import time

class CameraThread(QThread):
    """
    Dedicated thread for capturing video frames.
    Uses a latest-frame-only approach to prevent frame queue buildup.
    """
    frame_received = pyqtSignal(np.ndarray)
    
    def __init__(self, source=0):
        super().__init__()
        self.source = source
        self.running = True
        self.cap = None
        self._latest_frame = None
        self._mutex = QMutex()

    def run(self):
        # Use DirectShow backend on Windows for faster camera init
        if isinstance(self.source, int):
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(self.source)
        
        # Optimize camera settings
        if isinstance(self.source, int):
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self._mutex.lock()
                self._latest_frame = frame
                self._mutex.unlock()
                self.frame_received.emit(frame)
            else:
                if isinstance(self.source, str):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                else:
                    time.sleep(0.03)

        self.cap.release()

    def get_latest_frame(self):
        """Get the most recent frame, dropping any stale ones."""
        self._mutex.lock()
        frame = self._latest_frame
        self._latest_frame = None
        self._mutex.unlock()
        return frame

    def stop(self):
        self.running = False
        self.wait()

