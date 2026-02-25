"""
Smart Traffic - GPU Batch-wise Resumable YOLO Training
======================================================
Trains in batches of N epochs with auto-resume from checkpoint.
Prevents laptop overheating by pausing between batches.

Usage:
    python train_gpu_batch.py                    # Default: 25 epochs per batch, 100 total
    python train_gpu_batch.py --batch-epochs 10  # 10 epochs per batch
    python train_gpu_batch.py --resume           # Resume from last checkpoint
    python train_gpu_batch.py --total-epochs 50  # Train only 50 epochs total
"""
import sys
import os
import time
import argparse
import glob

# Use local libs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libs'))

import torch
from ultralytics import YOLO


def find_latest_checkpoint():
    """Find the most recent last.pt checkpoint."""
    patterns = [
        os.path.join('runs', 'detect', '**', 'weights', 'last.pt'),
    ]
    checkpoints = []
    for pattern in patterns:
        checkpoints.extend(glob.glob(pattern, recursive=True))
    
    if not checkpoints:
        return None
    
    # Return the most recently modified
    return max(checkpoints, key=os.path.getmtime)


def main():
    parser = argparse.ArgumentParser(description='GPU Batch-wise YOLO Training')
    parser.add_argument('--batch-epochs', type=int, default=25,
                        help='Epochs per batch (default: 25)')
    parser.add_argument('--total-epochs', type=int, default=100,
                        help='Total epochs to train (default: 100)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from latest checkpoint')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='Image size (default: 640)')
    parser.add_argument('--batch-size', type=int, default=0,
                        help='Batch size (0=auto, default: 0 for auto)')
    parser.add_argument('--cooldown', type=int, default=30,
                        help='Cooldown seconds between batches (default: 30)')
    args = parser.parse_args()

    data_yaml = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'tools', 'training_data', 'data.yaml')

    if not os.path.exists(data_yaml):
        print(f"ERROR: {data_yaml} not found!")
        return

    # ── Device Detection ──
    print("=" * 60)
    print("   Smart Traffic - GPU Batch Training")
    print("=" * 60)

    if torch.cuda.is_available():
        device = 0
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"  GPU: {gpu_name} ({gpu_mem:.1f} GB)")
        # For 4GB VRAM GPUs, use batch=2; auto mode may OOM
        if args.batch_size == 0:
            if gpu_mem < 5:
                batch_size = 4  # Safe for 4GB VRAM
            elif gpu_mem < 9:
                batch_size = 8
            else:
                batch_size = 16
        else:
            batch_size = args.batch_size
    else:
        device = 'cpu'
        print("  WARNING: No GPU detected! Falling back to CPU.")
        print("  Make sure CUDA PyTorch is installed:")
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu128 --target=libs")
        batch_size = args.batch_size if args.batch_size > 0 else 4

    print(f"  Device: {'GPU' if device == 0 else 'CPU'}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Image Size: {args.imgsz}")
    print(f"  Total Epochs: {args.total_epochs}")
    print(f"  Epochs per Batch: {args.batch_epochs}")
    print(f"  Cooldown: {args.cooldown}s between batches")
    print(f"  Data: {data_yaml}")
    print("=" * 60)

    # ── Find or load model ──
    checkpoint = find_latest_checkpoint()

    # Find best.pt dynamically (YOLO nests paths)
    best_candidates = glob.glob(os.path.join('runs', 'detect', '**', 'smart_traffic_gpu', 'weights', 'best.pt'), recursive=True)
    best_model_path = max(best_candidates, key=os.path.getmtime) if best_candidates else None
    if best_model_path:
        print(f"\n  Found previous best model: {best_model_path}")

    if args.resume and checkpoint:
        print(f"\n  Resuming from checkpoint: {checkpoint}")
        model = YOLO(checkpoint)
        results = model.train(
            resume=True,
            device=device,
            batch=batch_size,
        )
        print("\n" + "=" * 60)
        print("  Training Complete (Resumed)!")
        print("=" * 60)
    else:
        # ── Batch-wise training ──
        epochs_done = 0
        batch_num = 0

        while epochs_done < args.total_epochs:
            batch_num += 1
            remaining = args.total_epochs - epochs_done
            current_batch_epochs = min(args.batch_epochs, remaining)

            print(f"\n{'─' * 60}")
            print(f"  BATCH {batch_num}: Training {current_batch_epochs} epochs")
            print(f"  (Total progress: {epochs_done}/{args.total_epochs})")
            print(f"{'─' * 60}")

            if batch_num == 1 and not best_model_path:
                # First batch: start fresh from base model
                model = YOLO('yolov8n.pt')
            else:
                # Subsequent batches: load best model from previous batch
                # This uses transfer learning (not resume) so each batch
                # runs independently for N epochs
                if best_model_path and os.path.exists(best_model_path):
                    print(f"  Loading best model: {best_model_path}")
                    model = YOLO(best_model_path)
                else:
                    cp = find_latest_checkpoint()
                    if cp:
                        print(f"  Loading checkpoint: {cp}")
                        model = YOLO(cp)
                    else:
                        print("  No checkpoint found, starting fresh...")
                        model = YOLO('yolov8n.pt')

            results = model.train(
                data=data_yaml,
                epochs=current_batch_epochs,
                imgsz=args.imgsz,
                batch=batch_size,
                patience=0,  # Disable early stopping for batch training
                device=device,
                workers=0,
                project='runs/detect',
                name='smart_traffic_gpu',
                exist_ok=True,
                verbose=True,
                save=True,
                save_period=5,  # Save checkpoint every 5 epochs
            )

            epochs_done += current_batch_epochs

            if epochs_done < args.total_epochs:
                print(f"\n  Batch {batch_num} done! Cooling down for {args.cooldown}s...")
                print(f"  Progress: {epochs_done}/{args.total_epochs} epochs")
                if device == 0:
                    torch.cuda.empty_cache()  # Free GPU memory
                time.sleep(args.cooldown)

        print("\n" + "=" * 60)
        print("  ALL TRAINING COMPLETE!")
        print(f"  Total epochs: {epochs_done}")
        if best_model_path and os.path.exists(best_model_path):
            print(f"  Best model: {best_model_path}")
        print("=" * 60)


if __name__ == "__main__":
    main()
