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
import os, shutil, subprocess, sys, tarfile, time
from pathlib import Path

# A plain `pip install ultralytics` resolves torch/torchvision itself and can pull a fresh
# CPU-only wheel from PyPI, silently REPLACING Kaggle's pre-installed CUDA build. That is
# invisible until training starts -- "torch-...+cpu" in the startup banner and 0 GPUs found is
# the tell, seen on a live run here.
#
# Pin what is ALREADY installed via a constraints file instead of `--no-deps` with a guessed
# package list: pip still resolves and installs everything ultralytics needs (opencv, pyyaml,
# ultralytics-thop, whatever Kaggle's image does not already carry), it is simply forbidden from
# touching torch or torchvision, which stay exactly the CUDA build the image shipped with.
import importlib.metadata as _md
def _installed(pkg):
    try:
        return _md.version(pkg)
    except _md.PackageNotFoundError:
        return None

# Pinning only protects a torch that is CURRENTLY the CUDA build. If an earlier cell run in this
# same kernel already swapped it for a CPU wheel -- pip does not undo that on a re-run, and
# neither does re-running this cell -- pinning would lock in the ALREADY-BROKEN version instead
# of fixing anything. Catch that here, before spending a minute reinstalling for nothing: pip
# cannot put the CUDA build back (that only exists baked into a fresh session), so the one fix is
# Kaggle's own "Restart Session", which discards the kernel and reprovisions the GPU image clean.
_torch_now = _installed("torch")
if _torch_now and "+cpu" in _torch_now:
    raise SystemExit(
        f"torch is ALREADY {_torch_now} in this session -- a previous cell run (this one, before "
        f"a fix, or any other pip install) already replaced Kaggle's CUDA build, and nothing run "
        f"from here can put it back.\n"
        f"Fix: the menu above the notebook -> Run -> Restart Session (or the restart icon). That "
        f"discards this kernel and starts a clean one with the CUDA torch Kaggle provisions by "
        f"default. Then Run All again -- do not just re-run this cell.")

_pins = Path("/tmp/torch_pins.txt")
_pins.write_text("\n".join(f"{p}=={v}" for p in ("torch", "torchvision")
                           if (v := _installed(p))))
subprocess.run([sys.executable, "-m", "pip", "-q", "install", "-c", str(_pins), "ultralytics"],
              check=True)
import torch
from ultralytics import YOLO
assert torch.cuda.is_available(), (
    f"no CUDA: torch is {torch.__version__}, was {_torch_now} before this cell ran (unchanged, "
    f"so the pin held) -- but CUDA is still not available. If Settings -> Accelerator is not "
    f"GPU T4 x2 / P100, set it and Restart Session; a running session keeps whatever "
    f"accelerator it started with even if you change the setting afterward.")

# Everything lands in writable scratch. /kaggle/input is READ-ONLY and ultralytics wants to write
# a *.cache next to the labels; it survives being unable to, but then re-scans 9,000 labels at
# the start of every run.
DATA = Path("/kaggle/temp/detect")
IN = Path("/kaggle/input")

if not (DATA / "classes.txt").is_file():
    t0 = time.time()
    # Two shapes, because Kaggle decompresses an uploaded .zip and leaves any other archive
    # alone. `detect-pack` puts the set in ONE tar inside the zip, so the dataset is a single
    # file -- Kaggle's own uploader crashes trying to list ~19,000. Loose files still work.
    #
    # RECURSIVE, not a fixed depth. A dataset attached via "+ Add Input" lands under
    # /kaggle/input/<slug> (one level) on some accounts and under
    # /kaggle/input/datasets/<user>/<dataset-name> (three levels) on others -- observed both.
    # rglob walks to whatever depth Kaggle actually used instead of guessing it.
    loose = next((p.parent for p in IN.rglob("classes.txt")), None)
    tar = next(IN.rglob("*.tar"), None)
    if loose:
        shutil.copytree(loose, DATA)
        print(f"copied {loose.name} to scratch in {time.time() - t0:.0f}s")
    elif tar:
        DATA.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar) as t:
            # filter="data" refuses absolute paths and ../ escapes; it is Python 3.12+, and the
            # archive is ours either way, so fall back rather than fail on an older image.
            try:
                t.extractall(DATA, filter="data")
            except TypeError:
                t.extractall(DATA)
        print(f"extracted {tar.name} in {time.time() - t0:.0f}s")
    else:
        raise SystemExit("no classes.txt and no .tar under /kaggle/input -- add the dataset "
                         "via '+ Add Input' on the right")

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

# batch=-1 (AutoBatch) is a single-GPU feature -- ultralytics raises ValueError under Multi-GPU
# and asks for a fixed batch instead, seen on a live run here. Rather than guess one number for
# whatever card Kaggle happens to grant (a T4 today might be a P100 or something else next time),
# reuse ultralytics' OWN memory probe: run AutoBatch once on GPU 0 alone -- exactly what it would
# do for a single-GPU run -- to get a safe per-card batch, then multiply by the GPU count. That
# keeps the actual choice tied to the real card, not to a constant that goes stale.
batch = -1
if n_gpu > 1:
    import copy
    from ultralytics.nn.tasks import DetectionModel
    from ultralytics.utils.autobatch import check_train_batch_size
    try:
        # NOT `YOLO(MODEL).model.to(0)` -- tried that first and it silently profiles the WRONG
        # model. A checkpoint loaded straight from disk still carries nc=80 (COCO) and lacks the
        # loss setup a real Trainer attaches, and check_train_batch_size profiles memory through a
        # full forward+backward, so both distort the reading. Measured on the local 3070 against
        # the true value from an actual training run (batch=3 for yolo11s/nc=225/imgsz=960): the
        # naive probe said 20 -- 6.7x too high, an OOM waiting to happen hours into a rented run.
        # Rebuilding via DetectionModel with the real class count matched that true batch=3
        # exactly, for both yolo11s and this run's actual yolo11m.
        arch = copy.deepcopy(YOLO(MODEL).model.yaml)
        probe = DetectionModel(cfg=arch, ch=3, nc=len(names), verbose=False).to(0)
        per_gpu = check_train_batch_size(probe, imgsz=IMGSZ, amp=True)
        del probe
        torch.cuda.empty_cache()
        batch = per_gpu * n_gpu
        print(f"AutoBatch (multi-GPU unsupported) -- probed {per_gpu}/GPU on GPU0, "
              f"using batch={batch} across {n_gpu} GPUs")
    except Exception as exc:                                      # noqa: BLE001
        # A guessed number is still better than a crashed run: fall back to what the local 8 GB
        # card used for the smaller yolo11s (batch 3/GPU) -- conservative on a 15 GB T4, so the
        # risk is under-using memory, never an OOM hours into the run.
        torch.cuda.empty_cache()
        batch = 3 * n_gpu
        print(f"AutoBatch probe failed ({exc}); falling back to batch={batch} (3/GPU)")

YOLO(MODEL).train(
    data=str(DATA / "data.yaml"),
    epochs=EPOCHS, imgsz=IMGSZ, batch=batch, patience=30, seed=0,
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
