"""
Train YOLO model using labeled training data.
Uses local libs folder for PyTorch.
"""
import sys
import os

# Use local libs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libs'))

from ultralytics import YOLO

def main():
    data_yaml = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools', 'training_data', 'data.yaml')
    
    if not os.path.exists(data_yaml):
        print(f"ERROR: {data_yaml} not found!")
        return
    
    print("=" * 50)
    print("Smart Traffic - YOLO Training")
    print("=" * 50)
    print(f"Data: {data_yaml}")
    print(f"Model: yolov8n.pt (nano)")
    
    # Auto-detect GPU
    import torch
    if torch.cuda.is_available():
        device = 0  # GPU index
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
        print(f"Device: GPU ({gpu_name}, {gpu_mem:.1f}GB)")
        batch_size = 8  # Conservative for 4GB VRAM
    else:
        device = 'cpu'
        print("Device: CPU (no GPU detected)")
        batch_size = 4
    
    print(f"Epochs: 100")
    print(f"Batch Size: {batch_size}")
    print(f"Image Size: 640")
    print("=" * 50)
    
    # Load base model
    model = YOLO('yolov8n.pt')
    
    # Train
    results = model.train(
        data=data_yaml,
        epochs=100,
        imgsz=640,
        batch=batch_size,
        patience=20,
        device=device,
        workers=0,
        project='runs/detect',
        name='smart_traffic',
        exist_ok=True,
        verbose=True
    )
    
    print("\n" + "=" * 50)
    print("Training Complete!")
    print(f"Best model saved to: runs/detect/smart_traffic/weights/best.pt")
    print("=" * 50)

if __name__ == "__main__":
    main()
