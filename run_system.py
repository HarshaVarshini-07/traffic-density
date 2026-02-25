import sys
import os

# Ensure the root directory and libs are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(current_dir, "libs")
sys.path.insert(0, current_dir)
sys.path.insert(0, libs_dir)

# Register DLL directories for PyTorch CUDA on Windows
# This must happen BEFORE importing torch/ultralytics
if sys.platform == "win32":
    torch_lib = os.path.join(libs_dir, "torch", "lib")
    if os.path.isdir(torch_lib):
        os.add_dll_directory(torch_lib)
    # Also add NVIDIA/CUDA DLL paths if present
    nvidia_path = os.path.join(libs_dir, "nvidia")
    if os.path.isdir(nvidia_path):
        for sub in os.listdir(nvidia_path):
            bin_dir = os.path.join(nvidia_path, sub, "bin")
            lib_dir = os.path.join(nvidia_path, sub, "lib")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)
            if os.path.isdir(lib_dir):
                os.add_dll_directory(lib_dir)

# Pre-import torch BEFORE PyQt6 to prevent DLL conflicts
# PyQt6 can load conflicting DLLs that interfere with c10.dll
try:
    import torch
    print(f"PyTorch {torch.__version__} loaded (CUDA: {torch.cuda.is_available()})")
except Exception as e:
    print(f"Warning: PyTorch pre-import failed: {e}")

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

