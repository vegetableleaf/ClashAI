# ClashAI -- vision detector, trained on a rented GPU.
#
# Paste this into ONE Kaggle notebook cell and run it. Settings -> Accelerator -> GPU T4 x2
# (or P100), and Settings -> Internet -> On (needed once, to fetch the yolo11 backbone).
#
# Why this exists: the 3070 at home has 8 GB, which at imgsz 960 forces batch 3 and caps the
# model at yolo11s. The data problem is solved (38,265 boxes); the model size is now the ceiling.
#
# The val split rides along in the zip ON PURPOSE. Scoring the result on the same 401 images the
# local model was scored on is the only thing that makes "better" mean anything.

MODEL   = "yolo11m.pt"   # yolo11s.pt is what 8 GB allowed; m is the point of renting a card
EPOCHS  = 60             # the local run was still climbing at 60, so this is a floor, not a cap
IMGSZ   = 960            # units are small on the board -- do not lower this to buy speed

# ---------------------------------------------------------------- setup
import os, shutil, subprocess, sys, time
from pathlib import Path

subprocess.run([sys.executable, "-m", "pip", "-q", "install", "ultralytics"], check=True)
import torch
from ultralytics import YOLO

# Find the uploaded dataset without hard-coding the slug Kaggle assigns.
IN = next((p for p in Path("/kaggle/input").glob("*") if (p / "classes.txt").is_file()), None)
assert IN, "no dataset with classes.txt under /kaggle/input -- add it via '+ Add Input'"

# Copy to writable scratch: ultralytics writes a *.cache next to the labels, and /kaggle/input
# is read-only. It survives that, but re-scans 9,000 labels EVERY epoch-0 of every restart.
DATA = Path("/kaggle/temp/detect")
if not DATA.is_dir():
    t0 = time.time()
    shutil.copytree(IN, DATA)
    print(f"copied dataset to scratch in {time.time() - t0:.0f}s")

# ------------------------------------------------------- data.yaml
# Built HERE, from classes.txt, never shipped in the zip: the local data.yaml carries an absolute
# Windows path. classes.txt is also the only place the class ORDER may come from -- a names list
# that drifted from it would silently relabel every box in the set.
names = [c for c in (DATA / "classes.txt").read_text().split() if c]
train_dirs = ["images/train"] + (["synth/images"] if (DATA / "synth/images").is_dir() else [])
yaml_txt = (f"path: {DATA}\ntrain:\n" + "".join(f"  - {d}\n" for d in train_dirs)
            + f"val: images/val\nnc: {len(names)}\nnames:\n"
            + "".join(f"  {i}: {n}\n" for i, n in enumerate(names)))
(DATA / "data.yaml").write_text(yaml_txt)
print(f"{len(names)} classes | "
      f"{len(list((DATA/'images/train').glob('*.jpg')))} train + "
      f"{len(list((DATA/'images/val').glob('*.jpg')))} val frames")

# ---------------------------------------------------------------- train
n_gpu = torch.cuda.device_count()
print(f"{n_gpu} GPU(s): " + ", ".join(torch.cuda.get_device_name(i) for i in range(n_gpu)))

YOLO(MODEL).train(
    data=str(DATA / "data.yaml"),
    epochs=EPOCHS, imgsz=IMGSZ, batch=-1, patience=30, seed=0,
    device=list(range(n_gpu)) if n_gpu > 1 else 0,
    project="/kaggle/working/runs", name="vision", exist_ok=True,
    # Identical to the local run, so the comparison is of the MODEL and nothing else.
    # Colour jitter carries the blue own-troop labels over to the red enemy side (and covers
    # slow/rage tints); no horizontal flip, because the lanes are not symmetric.
    hsv_h=0.5, hsv_s=0.5, hsv_v=0.4, fliplr=0.0, erasing=0.4,
    # A Kaggle session is capped at 12h and can be cut short. Without this, a run that dies at
    # hour 11 leaves nothing at all; with it, the newest checkpoint is already in the output.
    save_period=5,
)

# ---------------------------------------------------------------- report
import csv
rows = list(csv.DictReader(open("/kaggle/working/runs/vision/results.csv")))
fit = lambda r: 0.1 * float(r["metrics/mAP50(B)"]) + 0.9 * float(r["metrics/mAP50-95(B)"])
best = max(rows, key=fit)          # ultralytics ranks by fitness, so best.pt IS this row
print(f"\n{len(rows)} epochs, best is epoch {best['epoch']}")
print(f"  mAP50     {float(best['metrics/mAP50(B)']):.4f}   (local yolo11s: 0.7754)")
print(f"  mAP50-95  {float(best['metrics/mAP50-95(B)']):.4f}   (local yolo11s: 0.5335)")
print(f"  recall    {float(best['metrics/recall(B)']):.4f}   (local yolo11s: 0.6849)")
print("\ndownload /kaggle/working/runs/vision/weights/best.pt from the Output tab")
