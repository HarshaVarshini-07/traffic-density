import sys
import os

# Ensure the root directory and libs are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "libs"))

try:
    from src.gui.main_window_v2 import MainWindow
    from src.core.processor import VideoProcessor
    from src.core.logger import DataLogger
    print("[OK] All GUI and Core modules imported successfully.")
except Exception as e:
    print(f"[FAIL] Import Error: {e}")
