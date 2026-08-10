"""Train the board object detector (Ultralytics) on the dataset built by
`run.py autolabel` plus your hand-labelled frames.

Defaults to YOLO11 (a CNN detector). Chosen over RT-DETR for THIS project: on a small,
label-bottlenecked, many-class (200+) custom dataset the transformer's accuracy edge doesn't
materialise (DETR-family models are data-hungry), while YOLO11 keeps a high imgsz affordable
(CR units are small), trains faster, and is lighter to run live alongside the policy. The
default is YOLO11x -- the LARGEST YOLO11 (highest accuracy ceiling, exceeds RT-DETR-L on COCO).
Note it is BIGGER than rtdetr-l, so at imgsz 960 auto-batch may shrink the batch (or OOM) --
step down to l/m/s for less VRAM / faster training. Pass an rtdetr* model to use RT-DETR instead
-- the dataset format is identical, so nothing else in the pipeline changes.

One-time setup (installs Ultralytics; it will pull a compatible torch if needed):

    icebow\\.venv\\Scripts\\python.exe -m pip install ultralytics

Then, from the `icebow/` folder:

    icebow\\.venv\\Scripts\\python.exe tools\\detect\\train.py                       # YOLO11x (default, largest)
    icebow\\.venv\\Scripts\\python.exe tools\\detect\\train.py --model yolo11l.pt    # lighter / faster
    icebow\\.venv\\Scripts\\python.exe tools\\detect\\train.py --model yolo11s.pt    # lightest good option (tight VRAM)
    icebow\\.venv\\Scripts\\python.exe tools\\detect\\train.py --model rtdetr-l.pt   # RT-DETR instead

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


def _install_status_aug() -> str:
    """Monkeypatch Ultralytics' Albumentations pipeline to SIMULATE Clash Royale STATUS EFFECTS that
    distort a troop's appearance: slow/rage COLOUR TINTS (blue/purple), spell/effect HAZE + partial-
    occlusion shadow, and effect BLUR. All PIXEL-ONLY (bbox-safe -- boxes never move). Needs the
    `albumentations` package; a graceful NO-OP if it's missing or the API differs (returns a note).
    Every step is guarded so it can never crash training -- worst case it falls back to the default."""
    try:
        import albumentations as A
        from ultralytics.data import augment as _aug
    except Exception:
        return ("albumentations MISSING -> tint/haze/blur skipped (occlusion via erasing still applies). "
                "For the full effect:  .venv\\Scripts\\python.exe -m pip install albumentations")
    tfs, names = [], []
    for name, make in (
        ("tint",   lambda: A.RGBShift(r_shift_limit=22, g_shift_limit=22, b_shift_limit=22, p=0.20)),
        ("bright", lambda: A.RandomBrightnessContrast(p=0.15)),
        ("haze",   lambda: A.RandomFog(p=0.08)),
        ("shadow", lambda: A.RandomShadow(p=0.05)),
        ("blur",   lambda: A.Blur(blur_limit=3, p=0.08)),
        ("mblur",  lambda: A.MedianBlur(blur_limit=3, p=0.05)),
    ):
        try:
            tfs.append(make()); names.append(name)
        except Exception:
            pass
    if not tfs:
        return "albumentations present but no transforms built (API mismatch) -> tint/haze/blur skipped"
    _orig = _aug.Albumentations.__init__

    def _patched(self, p=1.0):
        try:
            _orig(self, p)      # build Ultralytics' defaults (sets self.contains_spatial etc.)
            self.transform = A.Compose(
                tfs, bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]))
        except Exception:
            pass                # any failure -> keep whatever _orig set

    _aug.Albumentations.__init__ = _patched
    return "status-aug (Albumentations): " + ", ".join(names)


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the board detector (Ultralytics YOLO / RT-DETR).")
    ap.add_argument("--model", default="yolo11x.pt",
                    help="base weights: yolo11n/s/m/l/x.pt (YOLO, default x) or rtdetr-l/x.pt (RT-DETR)")
    ap.add_argument("--epochs", type=int, default=120, help="training epochs (early-stop via --patience)")
    ap.add_argument("--imgsz", type=int, default=960, help="train image size (the frame is tall ~668x1182)")
    ap.add_argument("--batch", type=int, default=-1,
                    help="images per batch; -1 auto-sizes to your GPU (drop to yolo11l/m/s.pt if VRAM is tight)")
    ap.add_argument("--patience", type=int, default=30, help="early-stop patience (epochs)")
    ap.add_argument("--seed", type=int, default=0,
                    help="training seed. Ultralytics runs seed=0 + deterministic=True, so re-running an "
                         "UNCHANGED dataset reproduces the same weights -- change this to get a genuine "
                         "replicate and measure the run-to-run noise floor (needed to know whether a "
                         "1-3pp gap between generations is real or seed variance)")
    ap.add_argument("--name", default="board",
                    help="run-folder prefix under runs/detect (ultralytics auto-increments: board -> board-24). "
                         "Use a different prefix for CONTROL runs so they do not consume the next board-N slot "
                         "-- a generation number should mean 'a candidate for promotion', not 'an experiment'.")
    ap.add_argument("--status-aug", action="store_true",
                    help="extra augmentation for CR STATUS EFFECTS that distort a troop's look: stronger OCCLUSION "
                         "(erasing 0.4->0.6) + colour-TINT (slow blue / rage purple), spell HAZE + BLUR via "
                         "Albumentations if installed. Default OFF (leaves training unchanged).")
    ap.add_argument("--resume", nargs="?", const="auto", default=None, metavar="RUN",
                    help="CONTINUE an interrupted run instead of starting a new one. Bare --resume picks the "
                         "newest runs/detect/*/weights/last.pt; pass a run name (e.g. board-17) to pick one. "
                         "Training dies quietly whenever its terminal is closed, and the run keeps its own "
                         "folder/epoch count/best.pt, so resuming loses nothing. All other flags are IGNORED -- "
                         "ultralytics restores them from the checkpoint's own args.")
    args = ap.parse_args()

    is_rtdetr = "rtdetr" in args.model.lower() or "rt-detr" in args.model.lower()
    try:
        from ultralytics import RTDETR, YOLO
    except ImportError:
        raise SystemExit("Ultralytics not installed. Run:  "
                         ".venv\\Scripts\\python.exe -m pip install ultralytics")

    root = Path(__file__).resolve().parents[2]           # icebow/
    data = root / "data" / "detect" / "data.yaml"
    if not data.exists():
        raise SystemExit(f"no dataset at {data}\n"
                         "Build it first:  run.py autolabel --all   (then hand-label the frames).")

    if args.resume:
        runs = root / "runs" / "detect"
        if args.resume == "auto":
            ckpts = sorted(runs.glob("*/weights/last.pt"), key=lambda p: p.stat().st_mtime)
            if not ckpts:
                raise SystemExit(f"no runs/detect/*/weights/last.pt to resume under {runs}")
            ckpt = ckpts[-1]
        else:
            ckpt = runs / args.resume / "weights" / "last.pt"
            if not ckpt.exists():
                raise SystemExit(f"no checkpoint at {ckpt}")
        print(f"[train] RESUMING {ckpt.parents[1].name} from {ckpt}")
        (RTDETR if is_rtdetr else YOLO)(str(ckpt)).train(resume=True)
        print(f"done -> {ckpt.parents[0] / 'best.pt'}")
        return

    model = (RTDETR if is_rtdetr else YOLO)(args.model)
    print(f"[train] {'RT-DETR' if is_rtdetr else 'YOLO'} from {args.model}  ->  {data}")
    erasing = 0.4                                        # random-erasing (occlusion) prob; raised by --status-aug
    if args.status_aug:
        erasing = 0.6                                    # spells/attacks/overlaps clouding a troop = partial occlusion
        print("[train] " + _install_status_aug())
    model.train(
        data=str(data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        patience=args.patience, seed=args.seed,
        project=str(root / "runs" / "detect"), name=args.name,
        # colour jitter helps the own-troop (blue) labels transfer to the red enemy side (also covers slow/rage tints)
        hsv_h=0.5, hsv_s=0.5, hsv_v=0.4, fliplr=0.0, erasing=erasing,   # no horizontal flip: lanes are asymmetric
    )
    print(f"done -> runs/detect/{args.name}*/weights/best.pt")


if __name__ == "__main__":
    main()
