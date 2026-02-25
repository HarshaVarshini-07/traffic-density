import sys
import os

# Include local libs folder
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "libs"))

def check_import(module_name, package_name=None):
    if package_name is None:
        package_name = module_name
    try:
        __import__(module_name)
        print(f"[OK] {package_name} is installed.")
        return True
    except ImportError as e:
        print(f"[FAIL] {package_name} is NOT installed. Error: {e}")
        return False

print("Verifying Dependencies...")
all_good = True

# Core
all_good &= check_import("cv2", "opencv-python")
all_good &= check_import("numpy")
all_good &= check_import("ultralytics")
all_good &= check_import("supervision")
all_good &= check_import("PyQt6", "PyQt6")

# Hardware (Optional but good to check)
try:
    import serial
    print("[OK] pyserial is installed.")
except ImportError:
    print("[WARN] pyserial is missing (needed for Arduino).")
    # Not critical for GUI demo, but needed for full system

if all_good:
    print("\nSUCCESS: All core dependencies are installed and ready!")
else:
    print("\nERROR: Some dependencies are missing. Run: pip install -r requirements.txt")
