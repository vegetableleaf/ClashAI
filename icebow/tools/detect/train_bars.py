"""Train the 2-class HP-bar detector built by build_bars.py.

Deliberately NOT tools/detect/train.py: that one owns runs/detect/vision, the single
operating detector, and its folder lock stops two runs fighting over that directory. This
writes runs/bars/ instead, so the folder lock does not apply -- but the GPU is shared, and
two trainings on one 8 GB card OOM rather than take turns. So this claims the same GPU lock
train.py does: whichever starts second is refused with a message instead of dying silently.

`yolo11n`, not `s` or `m`: two geometrically simple classes over 37k boxes. The capacity is
not what limits this; input resolution is. Bars are a few dozen pixels wide, so imgsz stays
at 960 to match the main detector -- shrinking it is what would actually cost accuracy.

    python icebow/tools/detect/train_bars.py [--epochs 40] [--model yolo11n.pt]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]  # icebow/


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--imgsz", type=int, default=960)
    # -1 is AutoBatch. Safe here because this is ONE GPU -- AutoBatch is what broke the
    # Kaggle 2xT4 run, and that failure was multi-GPU specific.
    ap.add_argument("--batch", type=int, default=-1)
    a = ap.parse_args()

    data = HERE / "data" / "bars" / "data.yaml"
    if not data.is_file():
        raise SystemExit(f"{data} missing -- run build_bars.py first")

    # Claimed BEFORE ultralytics is imported: refusing should cost a second, not the ~10 s
    # torch takes to load, and it must happen before anything touches CUDA.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from train import claim_gpu                                    # noqa: E402
    claim_gpu(HERE / "runs", "bars")

    from ultralytics import YOLO

    YOLO(a.model).train(
        data=str(data),
        imgsz=a.imgsz,
        epochs=a.epochs,
        batch=a.batch,
        project=str(HERE / "runs" / "bars"),
        name="v1",
        exist_ok=True,
        patience=10,
        save_period=5,   # the Kaggle lesson: a run that dies at epoch 31 should not cost 31 epochs
    )


if __name__ == "__main__":
    main()
