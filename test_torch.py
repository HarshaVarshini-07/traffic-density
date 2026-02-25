import sys
import os

# Include local libs folder
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "libs"))

try:
    import torch
    print(f"Torch imported successfully. Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"Torch import failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
