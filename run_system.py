import sys
import os

# Ensure the root directory and libs are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "libs"))

from PyQt6.QtWidgets import QApplication
from src.gui.main_window_v2 import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Set Metadata
    app.setApplicationName("Smart Traffic Manager")
    app.setApplicationVersion("2.0")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
