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

Weights land in runs/detect/vision/weights/best.pt -- ALWAYS that path. There is exactly one
vision model in this project and a retrain replaces it. Once you're happy with the mAP, wire the
detector into the observation (Stage 3): render its detections into semantic map channels fed
to PolicyNet alongside the arena image, then re-derive the dataset + retrain BC and RL.

NOTE: the auto (own-troop) labels only cover the units YOU play. Before training seriously,
open the exported frames in a labeller and add the ENEMY units (and any own units the
auto-pass missed) -- a detector trained on partially-labelled frames learns to ignore the
unlabelled units. Start with a few hundred well-labelled frames.
"""
from __future__ import annotations

import argparse
import atexit
import os
import shutil
from pathlib import Path
from typing import Optional

# The ONE vision model's folder. Everything that loads a detector resolves to
# runs/detect/<RUN_NAME>/weights/best.pt; see detect._resolve_weights.
RUN_NAME = "vision"


def _auto_model(imgsz: int) -> str:
    """Largest yolo11 backbone that fits this GPU at `imgsz`.

    yolo11 n/s/m/l/x are the SAME architecture at five sizes -- a starting point, not five
    models, and training collapses whichever you pick into the one detector at
    runs/detect/vision. Offering the list as a dropdown made it read as five competing
    models, so the choice is made here from measured VRAM and merely printed.

    Thresholds are for imgsz 960 with ultralytics' auto-batch, which is where this project
    trains; anything smaller leaves headroom, so the bound scales with the area.
    """
    need = {"yolo11x.pt": 22.0, "yolo11l.pt": 14.0, "yolo11m.pt": 10.0, "yolo11s.pt": 6.0}
    try:
        import torch
        if not torch.cuda.is_available():
            print("[train] no CUDA -> yolo11n.pt (CPU training is slow; expect hours)")
            return "yolo11n.pt"
        gb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    except Exception:                                    # noqa: BLE001 -- torch missing/odd driver
        return "yolo11s.pt"
    scale = max(0.35, (imgsz / 960.0) ** 2)              # VRAM tracks pixel count
    for name, want in need.items():
        if gb >= want * scale:
            print(f"[train] {gb:.0f} GB VRAM at imgsz {imgsz} -> {name} "
                  "(size only; the result is still ONE detector)")
            return name
    print(f"[train] {gb:.0f} GB VRAM at imgsz {imgsz} -> yolo11n.pt (smallest that fits)")
    return "yolo11n.pt"


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


def _fitness_of(pt: Path) -> float:
    """The `best_fitness` ultralytics stored in a checkpoint, or -1 if it cannot be read.

    -1, not 0: an unreadable file must never win a comparison against a real model."""
    try:
        import torch
        ck = torch.load(pt, map_location="cpu", weights_only=False)
        f = ck.get("best_fitness")
        return float(f) if f is not None else -1.0
    except Exception:                                    # noqa: BLE001
        return -1.0


def _keep_previous(best: Path) -> None:
    """Copy best.pt aside -- but NEVER over a better copy that is already there.

    An unconditional copy is worse than none. Starting a second run twenty minutes into the
    first overwrote the good model (fitness 0.477) with that run's epoch-2 weights (0.184), so
    the safety net held the very thing it existed to protect against. Compare and keep the better
    one: the point is a way BACK, and the way back is whichever model is actually best."""
    keep = best.with_name("best_previous.pt")
    now, had = _fitness_of(best), (_fitness_of(keep) if keep.exists() else -1.0)
    if had > now:
        print(f"[train] {keep.name} already holds a BETTER model (fitness {had:.4f} vs {now:.4f}) "
              f"-- keeping it, not overwriting with the weaker one")
        return
    shutil.copyfile(best, keep)
    print(f"[train] kept the model you have now as {keep.name} (fitness {now:.4f}) -- this run "
          f"overwrites best.pt from epoch 1, so that copy is the way back if it ends up worse")


def _holder(lock: Path) -> Optional[int]:
    """PID currently holding `lock`, or None if it is free or stale."""
    if not lock.is_file():
        return None
    try:
        pid = int(lock.read_text(encoding="utf-8").strip() or 0)
    except (ValueError, OSError):
        return None
    if not pid:
        return None
    try:
        import psutil                                    # already an ultralytics dependency
        return pid if psutil.pid_exists(pid) else None
    except Exception:                                    # noqa: BLE001
        return pid                                       # cannot tell -> assume held, refuse


def claim_gpu(runs_root: Path, what: str) -> None:
    """Refuse to start if ANOTHER training already has this GPU.

    The folder lock below only knows about other runs writing the SAME folder. It cannot see a
    second trainer writing somewhere else -- runs/bars, say -- and that one is just as fatal:
    two trainings on one 8 GB card do not queue, they OOM, and the loser dies with an error the
    panel never shows. A separate lock beside the run folders covers the resource rather than
    the directory, so a clear refusal replaces a silent crash.

    Deliberately NOT the same file as the folder lock: they answer different questions, and
    merging them would let a CPU-only job block the GPU or the reverse.
    """
    lock = runs_root / ".gpu.pid"
    pid = _holder(lock)
    if pid and pid != os.getpid():
        raise SystemExit(
            f"another training already has the GPU (process {pid}).\n"
            f"Two trainings on one card run out of memory instead of taking turns, and the one "
            f"that loses dies without a message anyone sees. Wait for it, or stop it first.\n"
            f"If you are sure nothing is running, delete {lock}.")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(lambda: lock.unlink(missing_ok=True))
    print(f"[{what}] holding the GPU lock ({lock})")


def _claim(run_dir: Path) -> None:
    """Refuse to start if another training is already writing to this folder.

    There is deliberately one run folder, and `exist_ok=True` lets a second run walk straight into
    it: both then fight over best.pt, last.pt and results.csv. Seen exactly that -- a second start
    truncated results.csv (losing the curve the panel draws) and clobbered the backup, then died
    on VRAM a minute later having written no error anyone could see. Failing loudly here beats
    corrupting the first run's output and dying quietly."""
    lock = run_dir / ".training.pid"
    if lock.is_file():
        try:
            pid = int(lock.read_text(encoding="utf-8").strip() or 0)
        except ValueError:
            pid = 0
        alive = False
        if pid:
            try:
                import psutil                            # already an ultralytics dependency
                alive = psutil.pid_exists(pid)
            except Exception:                            # noqa: BLE001
                alive = True                             # cannot tell -> assume it is, and refuse
        if alive:
            raise SystemExit(
                f"a training is ALREADY running in {run_dir.name} (process {pid}).\n"
                f"Two runs in one folder overwrite each other's model and blank the progress "
                f"curve, and the second one dies on VRAM anyway. Wait for it, or stop it first.\n"
                f"If you are sure nothing is running, delete {lock}.")
        print(f"[train] ignoring a stale lock from process {pid} (no longer running)")
    run_dir.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(lambda: lock.unlink(missing_ok=True))


def _resumable(ckpt: Path) -> bool:
    """Does this checkpoint still carry the TRAINING state ultralytics needs to resume?

    A run that finished (or was stripped) keeps only inference weights. `resume=True` on such a file
    is not an error to ultralytics -- it warns and quietly starts a new training on its default
    dataset -- so the caller has to check first. Any read failure is treated as NOT resumable: the
    conservative answer is the one that does not waste a GPU-day on coco8.
    """
    try:
        import torch
        ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the board detector (Ultralytics YOLO / RT-DETR).")
    ap.add_argument("--model", default="auto", metavar="WEIGHTS",
                    help="ADVANCED. Leave this alone. `auto` (default) CONTINUES the vision model "
                         "you already have, and only if none exists picks a pretrained backbone "
                         "sized to this GPU's VRAM. There is one detector either way -- yolo11 "
                         "n/s/m/l/x are sizes of the same network, not rival models. Pass an "
                         "explicit path only to start from some other file.")
    ap.add_argument("--epochs", type=int, default=120, help="training epochs (early-stop via --patience)")
    ap.add_argument("--imgsz", type=int, default=960, help="train image size (the frame is tall ~668x1182)")
    # MERGE NOTE: upstream hardcodes 4 ("safe on VRAM for the board-24 setup") -- safe on THEIR
    # card. This branch measures instead: _auto_model() picks the backbone from actual VRAM and
    # -1 lets ultralytics' AutoBatch size the batch to whatever that leaves. A number tuned on
    # someone else's GPU is exactly the kind of borrowed constant that reads as a decision.
    ap.add_argument("--batch", type=int, default=-1,
                    help="images per batch; -1 auto-sizes to your GPU. Pin it only if AutoBatch "
                         "guesses high and the run dies out of memory.")
    ap.add_argument("--patience", type=int, default=30, help="early-stop patience (epochs)")
    ap.add_argument("--workers", type=int, default=8,
                    help="dataloader worker processes. EACH worker imports torch, so this is a major RAM "
                         "consumer: a board-24 run died with 'the paging file is too small' while a "
                         "32-env CPU train-sim-ppo was running alongside it. Drop to 2-4 when sharing the "
                         "machine with another training job; the run is GPU-bound, so throughput barely moves.")
    ap.add_argument("--seed", type=int, default=0,
                    help="training seed. Ultralytics runs seed=0 + deterministic=True, so re-running an "
                         "UNCHANGED dataset reproduces the same weights -- change this to get a genuine "
                         "replicate and measure the run-to-run noise floor (needed to know whether a "
                         "1-3pp gap between generations is real or seed variance)")
    # MERGE NOTE: upstream defaults this to "board" and lets ultralytics auto-increment into
    # board-22, board-23, board-24 ... one generation per run. This branch went the other way on
    # purpose (see the model.train call): there is ONE detector, at runs/detect/vision, and a
    # retrain replaces it -- the panel, detect._resolve_weights and ui/ckpt.py all read that one
    # path. Keeping their flag but OUR default means a deliberate side experiment still gets its
    # own folder, while the normal case cannot quietly fork the model into a pile of directories.
    ap.add_argument("--name", default=RUN_NAME,
                    help="run folder under runs/detect. Defaults to the ONE vision model's folder, "
                         "which a retrain replaces. Pass something else for a side experiment you "
                         "do not want installed as the operating detector.")
    ap.add_argument("--status-aug", action="store_true",
                    help="extra augmentation for CR STATUS EFFECTS that distort a troop's look: stronger OCCLUSION "
                         "(erasing 0.4->0.6) + colour-TINT (slow blue / rage purple), spell HAZE + BLUR via "
                         "Albumentations if installed. Default OFF (leaves training unchanged).")
    ap.add_argument("--fresh", action="store_true",
                    help="THROW AWAY what the vision model learned and start from a pretrained "
                         "backbone. Normally you do not want this: training already continues the "
                         "model you have. Use it only when the existing model is worse than "
                         "nothing -- e.g. it was fitted on labels that turned out to be wrong.")
    ap.add_argument("--resume", nargs="?", const="auto", default=None, metavar="RUN",
                    help="CONTINUE an interrupted run instead of starting a new one. Bare --resume picks the "
                         "runs/detect/vision/weights/last.pt; pass a folder name to pick a different one. "
                         "Training dies quietly whenever its terminal is closed, and the run keeps its own "
                         "folder/epoch count/best.pt, so resuming loses nothing. All other flags are IGNORED -- "
                         "ultralytics restores them from the checkpoint's own args.")
    args = ap.parse_args()
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

    # THE DEFAULT IS TO CARRY ON. There is one model; training it again on more pictures must
    # continue THAT model, not quietly begin a different one. Only when no model exists yet does
    # this fall back to a pretrained YOLO backbone -- and that is a starting point, not a choice
    # between models: you never see it unless there is nothing to continue.
    ours = root / "runs" / "detect" / RUN_NAME / "weights" / "best.pt"
    if args.model == "auto":
        if ours.exists() and not args.fresh:
            args.model = str(ours)
            print(f"[train] CONTINUING the vision model: {ours.relative_to(root)}")
            print("[train] (it keeps what it already learned and now also sees the new pictures; "
                  "--fresh starts over from a pretrained backbone instead)")
        else:
            args.model = _auto_model(args.imgsz)
            why = "starting over on request" if args.fresh else "no vision model yet"
            print(f"[train] {why} -> starting from {args.model}")
    elif args.fresh:
        raise SystemExit("--fresh and --model are contradictory: --fresh means 'ignore the model "
                         "we have', --model names exactly what to start from. Pick one.")

    is_rtdetr = "rtdetr" in args.model.lower() or "rt-detr" in args.model.lower()

    if args.resume:
        runs = root / "runs" / "detect"
        if args.resume == "auto":
            ckpt = runs / RUN_NAME / "weights" / "last.pt"
            if not ckpt.exists():
                raise SystemExit(f"nothing to resume: no {ckpt}")
        else:
            ckpt = runs / args.resume / "weights" / "last.pt"
            if not ckpt.exists():
                raise SystemExit(f"no checkpoint at {ckpt}")
        # A FINISHED (or externally stripped) run has had its optimizer/epoch state removed --
        # ultralytics strips last.pt/best.pt down to inference weights. Handing such a file to
        # resume=True does NOT raise: it prints a warning and silently starts a BRAND-NEW training
        # on its DEFAULT dataset (coco8.yaml, 80 classes) in a fresh runs/detect/train-N folder.
        # That has already happened three times in this repo (runs/detect/train, train-2, train-3),
        # burning GPU on a demo dataset while looking like a normal training log. Refuse instead.
        if not _resumable(ckpt):
            raise SystemExit(
                f"{ckpt} carries no optimizer/epoch state -- it is a STRIPPED (finished) checkpoint,\n"
                "so ultralytics cannot resume it and would silently start a NEW coco8 training.\n"
                "That run is over: evaluate it (`run.py detect-eval --weights "
                f"{ckpt.parents[1].name}/weights/best.pt --sweep --subset data/detect/val_board15.txt`)\n"
                "or start a fresh generation with `--name` instead.")
        print(f"[train] RESUMING {ckpt.parents[1].name} from {ckpt}")
        (RTDETR if is_rtdetr else YOLO)(str(ckpt)).train(resume=True)
        print(f"done -> {ckpt.parents[0] / 'best.pt'}")
        return

    run_dir = root / "runs" / "detect" / args.name
    claim_gpu(root / "runs", "train")
    _claim(run_dir)

    # ONE folder for one model (see the exist_ok note below) has a sharp edge: ultralytics
    # rewrites best.pt from epoch 1, so the moment a new run starts, the model you had is gone.
    # That is fine while the run improves on it and a disaster when it does not -- a fresh LR
    # warmup on a much larger dataset dips BELOW the starting point for the first epochs, and a
    # run stopped in that window leaves the panel installing weights worse than yesterday's with
    # nothing to fall back to. The copy is taken once, before the first epoch can overwrite it.
    if ours.exists():
        _keep_previous(ours)

    model = (RTDETR if is_rtdetr else YOLO)(args.model)
    print(f"[train] {'RT-DETR' if is_rtdetr else 'YOLO'} from {args.model}  ->  {data}")
    erasing = 0.4                                        # random-erasing (occlusion) prob; raised by --status-aug
    if args.status_aug:
        erasing = 0.6                                    # spells/attacks/overlaps clouding a troop = partial occlusion
        print("[train] " + _install_status_aug())
    # The card is written in a finally: a run you STOP still leaves best.pt installed, and
    # without this the panel goes on showing the previous run's numbers for weights that are no
    # longer there. Seen exactly that -- a run stopped at epoch 103 left a card from two days
    # earlier describing an 86-box model, so the panel reported 74.7% for a detector that had
    # been replaced.
    try:
        model.train(
            data=str(data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
            patience=args.patience, seed=args.seed,
            # MERGE NOTE: upstream's --workers is kept, their board-N run naming is not.
            # Their default is 8 and each worker imports torch, which killed one of their runs
            # with "the paging file is too small" while a 32-env train-sim-ppo ran beside it --
            # worth having on a machine that shares the GPU, which this one now does.
            workers=args.workers,
        # ONE vision model, always the same folder. Ultralytics' default (exist_ok=False)
        # auto-increments to board, board-2, board-3 ... which turns one network into a pile
        # of identically named directories, silently loads "whichever was newest", and makes
        # the count of models in this project unreadable. There is exactly one detector; a
        # retrain replaces it. --name still works for a deliberate side experiment, but it
        # defaults to that one folder rather than to the next generation number.
            project=str(root / "runs" / "detect"), name=args.name, exist_ok=True,
            # colour jitter helps the own-troop (blue) labels transfer to the red enemy side
            # (also covers slow/rage tints)
            hsv_h=0.5, hsv_s=0.5, hsv_v=0.4, fliplr=0.0,
            erasing=erasing,           # no horizontal flip: lanes are asymmetric
        )
        print(f"done -> runs/detect/{args.name}/weights/best.pt")
    finally:
        write_model_card(root / "runs" / "detect" / args.name, args)


def write_model_card(run_dir: Path, args) -> None:
    """Record what the weights on disk ARE, once a training finishes.

    Reusing one folder means a new run truncates results.csv the moment it starts -- so an
    aborted training leaves the previous (still installed) weights with no record of their
    quality at all. Measured that the hard way. The card is written only on COMPLETION, so it
    always describes best.pt as it currently stands, while results.csv stays free to show
    whatever is training right now.

    THE ROW IT DESCRIBES IS THE BEST ONE, NOT THE LAST. best.pt is the best epoch's weights, so
    a card built from the final row describes a checkpoint that is not on disk. Measured here:
    a run stopped at epoch 103 had best.pt from epoch 76 (mAP50 0.710) while its last row read
    0.695 -- the card would have understated the installed model and, worse, claimed numbers no
    file backs. Ultralytics ranks by FITNESS (0.1*mAP50 + 0.9*mAP50-95), so that is the ranking
    used here; picking the best mAP50 instead would name a different epoch than best.pt holds.
    """
    import json
    csv = run_dir / "results.csv"
    card = {"model": args.model, "imgsz": args.imgsz, "epochs_requested": args.epochs}
    try:
        lines = [ln for ln in csv.read_text(encoding="utf-8").splitlines() if ln.strip()]
        head = [c.strip() for c in lines[0].split(",")]
        rows = [dict(zip(head, ln.split(","))) for ln in lines[1:]]

        def _f(row, col):
            v = row.get(col)
            return float(v) if v not in (None, "", "nan") else None

        def _fitness(row):
            m50, m95 = _f(row, "metrics/mAP50(B)"), _f(row, "metrics/mAP50-95(B)")
            return 0.1 * (m50 or 0.0) + 0.9 * (m95 or 0.0)

        row = max(rows, key=_fitness) if rows else {}
        card["epochs_run"] = _f(rows[-1], "epoch") if rows else None
        for key, col in (("epochs", "epoch"), ("mAP50", "metrics/mAP50(B)"),
                         ("mAP50_95", "metrics/mAP50-95(B)"),
                         ("precision", "metrics/precision(B)"), ("recall", "metrics/recall(B)")):
            v = _f(row, col)
            if v is not None:
                card[key] = v
    except (OSError, ValueError, IndexError):
        pass
    try:
        det = run_dir.parents[2] / "data" / "detect"   # runs/detect/<run> -> icebow/
        # Count the splits SEPARATELY. This used to sum train+val into a field called
        # `trained_on_boxes`, which overstated the training set by the whole validation split
        # (1,452 of 37,768 boxes) and, worse, described data the model never saw as data it
        # was trained on. That number was copied into the hand-off spec before anyone checked.
        def _count(split: str) -> tuple[int, int]:
            ps = list((det / "labels" / split).glob("*.txt"))
            n = sum(len([ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()])
                    for p in ps)
            return len(ps), n

        card["trained_on_frames"], card["trained_on_boxes"] = _count("train")
        card["val_frames"], card["val_boxes"] = _count("val")
    except OSError:
        pass
    try:
        (run_dir / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
        print(f"[train] model card -> {run_dir / 'model_card.json'}")
    except OSError as exc:
        print(f"[train] could not write the model card: {exc}")


if __name__ == "__main__":
    main()
