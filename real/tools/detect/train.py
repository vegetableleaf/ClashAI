"""Train the board object detector (Ultralytics) on the dataset built by
`run.py autolabel` plus your hand-labelled frames.

Defaults to RT-DETR (a transformer detector -- more accurate than YOLO, a bit slower; inference
is still real-time and the bot only acts every ~1.5s). Pass a yolo* model to use YOLO instead --
the dataset format is identical, so nothing else in the pipeline changes.

One-time setup (installs Ultralytics; it will pull a compatible torch if needed):

    real\\.venv\\Scripts\\python.exe -m pip install ultralytics

Then, from the `real/` folder:

    real\\.venv\\Scripts\\python.exe tools\\detect\\train.py                       # RT-DETR-L (default)
    real\\.venv\\Scripts\\python.exe tools\\detect\\train.py --model rtdetr-x.pt   # bigger RT-DETR
    real\\.venv\\Scripts\\python.exe tools\\detect\\train.py --model yolo11s.pt    # YOLO instead

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
    ap = argparse.ArgumentParser(description="Train the board detector (Ultralytics RT-DETR / YOLO).")
    ap.add_argument("--model", default="rtdetr-l.pt",
                    help="base weights: rtdetr-l/x.pt (RT-DETR, default) or yolo11n/s/m.pt (YOLO)")
    ap.add_argument("--epochs", type=int, default=120, help="RT-DETR converges a bit slower than YOLO")
    ap.add_argument("--imgsz", type=int, default=960, help="train image size (the frame is tall ~668x1182)")
    ap.add_argument("--batch", type=int, default=-1,
                    help="images per batch; -1 auto-sizes to your GPU (RT-DETR-L is heavier than YOLO)")
    ap.add_argument("--patience", type=int, default=30, help="early-stop patience (epochs)")
    args = ap.parse_args()

    is_rtdetr = "rtdetr" in args.model.lower() or "rt-detr" in args.model.lower()
    try:
        from ultralytics import RTDETR, YOLO
    except ImportError:
        raise SystemExit("Ultralytics not installed. Run:  "
                         ".venv\\Scripts\\python.exe -m pip install ultralytics")

    root = Path(__file__).resolve().parents[2]           # real/
    data = root / "data" / "detect" / "data.yaml"
    if not data.exists():
        raise SystemExit(f"no dataset at {data}\n"
                         "Build it first:  run.py autolabel --all   (then hand-label the frames).")

    model = (RTDETR if is_rtdetr else YOLO)(args.model)
    print(f"[train] {'RT-DETR' if is_rtdetr else 'YOLO'} from {args.model}  ->  {data}")
    model.train(
        data=str(data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        patience=args.patience, project=str(root / "runs" / "detect"), name="board",
        # colour jitter helps the own-troop (blue) labels transfer to the red enemy side
        hsv_h=0.5, hsv_s=0.5, hsv_v=0.4, fliplr=0.0,   # no horizontal flip: lanes are asymmetric
    )
    print("done -> runs/detect/board/weights/best.pt")


if __name__ == "__main__":
    main()
