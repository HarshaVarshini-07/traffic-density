from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
import cv2
import numpy as np

class VideoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_label = QLabel("Camera Feed Offline")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000; border: 2px solid #333; border-radius: 8px;")
        self.video_label.setMinimumSize(640, 640) 
        
        self.layout.addWidget(self.video_label)

    @pyqtSlot(np.ndarray)
    def update_frame(self, frame):
        """Updates the video label with a new opencv frame."""
        if frame is None:
            return
            
        try:
            # Resize logic can be handled here or by QLabel scaling
            # Converting BGR to RGB
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Efficient scaling
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.video_label.width(), 
                self.video_label.height(), 
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.video_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Frame update error: {e}")
            
    def set_placeholder(self, text):
        self.video_label.setText(text)
        self.video_label.clear()
