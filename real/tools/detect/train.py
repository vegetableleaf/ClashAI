"""Train the board object detector (Ultralytics YOLO11) on the dataset built by
`run.py autolabel` plus your hand-labelled frames.

One-time setup (installs Ultralytics; it will pull a compatible torch if needed):

    real\\.venv\\Scripts\\python.exe -m pip install ultralytics

Then, from the `real/` folder:

    real\\.venv\\Scripts\\python.exe tools\\detect\\train.py            # yolo11n, quick
    real\\.venv\\Scripts\\python.exe tools\\detect\\train.py --model yolo11s.pt --epochs 200

Weights land in runs/detect/board/weights/best.pt. Once you're happy with the mAP, wire the
detector into the observation (Stage 3): render its detections into semantic map channels fed
to PolicyNet alongside the arena image, then re-derive the dataset + retrain BC and RL.

NOTE: the auto (own-troop) labels only cover the units YOU play. Before training seriously,
open the exported frames in a labeller and add the ENEMY units (and any own units the
auto-pass missed) -- a detector trained on partially-labelled frames learns to ignore the
unlabelled units. Start with a few hundred well-labelled frames.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the board detector (Ultralytics YOLO11).")
    ap.add_argument("--model", default="yolo11n.pt", help="base weights (yolo11n/s/m.pt)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=960, help="train image size (the frame is tall ~668x1182)")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--patience", type=int, default=20, help="early-stop patience (epochs)")
    args = ap.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("Ultralytics not installed. Run:  "
                         ".venv\\Scripts\\python.exe -m pip install ultralytics")

    root = Path(__file__).resolve().parents[2]           # real/
    data = root / "data" / "detect" / "data.yaml"
    if not data.exists():
        raise SystemExit(f"no dataset at {data}\n"
                         "Build it first:  run.py autolabel --all   (then hand-label the frames).")

    model = YOLO(args.model)
    model.train(
        data=str(data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        patience=args.patience, project=str(root / "runs" / "detect"), name="board",
        # colour jitter helps the own-troop (blue) labels transfer to the red enemy side
        hsv_h=0.5, hsv_s=0.5, hsv_v=0.4, fliplr=0.0,   # no horizontal flip: lanes are asymmetric
    )
    print("done -> runs/detect/board/weights/best.pt")


if __name__ == "__main__":
    main()
