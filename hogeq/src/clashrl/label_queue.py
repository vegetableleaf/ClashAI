r"""ACTIVE LABELLING QUEUE (`run.py label-queue`): rank the UNLABELLED frames by how much
labelling each one would actually teach the detector, instead of working through the queue in
whatever order the files landed.

WHY: the queue holds ~2600 frames and hand-labelling is the scarcest resource in this project.
Frames are NOT equally valuable -- a clean board the detector already reads perfectly teaches it
nothing, while a frame where it cannot decide between two cards is exactly the supervision that
resolves a confusion. Measured on board-16, the weak classes fail for THREE different reasons and
only one of them is fixed by more frames of the same kind:

  wizard   60% of its val boxes are given to the WRONG class (mostly musketeer) -> AMBIGUITY
  valkyrie 31% wrong class (some to knight)                                     -> AMBIGUITY
  guards   36% of its boxes are BLIND (nothing detected there at all)           -> COVERAGE
  knight   17% right-class-but-under-confident, only 11% wrong class            -> neither; a gate issue

So two scores are computed per frame and reported separately:

AMBIGUITY -- two DIFFERENT base classes claim the same box (IoU >= 0.5) with comparable confidence.
  This is the model saying "I cannot tell these apart here", which is precisely a disambiguation
  frame. Scored by the geometric mean of the two confidences times their similarity, so a 0.45-vs-
  0.40 standoff outranks a 0.80-vs-0.05 non-contest.

UNCERTAINTY -- a lone detection sitting in the middle confidence band (`--lo`..`--hi`). The model
  half-sees something; a label either confirms it (and pulls the confidence up) or marks it as
  background. Peaks in the middle of the band and falls off toward either end.

Frames already imported into train/val are skipped -- they are annotated. Nothing is moved or
deleted: the ranking is written as a stem list, and `--copy` additionally mirrors the top frames
into their own folder so Label Studio can point at just those.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .card_threat import base_key
from .detect_eval import _iou


def _score_frame(dets, targets, lo, hi):
    """(ambiguity, uncertainty, [notes]) for one frame's detections."""
    amb, unc, notes = 0.0, 0.0, []
    # AMBIGUITY: competing base classes on one box
    for i, (c1, n1, b1) in enumerate(dets):
        for c2, n2, b2 in dets[i + 1:]:
            if n1 == n2 or _iou(b1, b2) < 0.5:
                continue
            if targets and n1 not in targets and n2 not in targets:
                continue
            sim = min(c1, c2) / max(c1, c2)             # 1.0 = dead heat
            s = (c1 * c2) ** 0.5 * sim
            if s > amb:
                amb = s
            notes.append(f"{n1}={c1:.2f} vs {n2}={c2:.2f}")
    # UNCERTAINTY: mid-band lone detections
    for c, n, _b in dets:
        if targets and n not in targets:
            continue
        if lo <= c <= hi:
            mid = 1.0 - abs(c - (lo + hi) / 2) / ((hi - lo) / 2)   # 1.0 at band centre
            unc = max(unc, mid)
    return amb, unc, notes


def label_queue(cfg, classes=None, n=150, weights=None, lo=0.15, hi=0.60,
                device=None, limit=None, copy=False) -> None:
    from .detect import _load_classes, _resolve_weights

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    qdir = root / "images" / cfg.get("detect", "label_queue_subdir", default="to_label")
    if not qdir.is_dir():
        print(f"[label-queue] no queue folder at {qdir}")
        return

    names = _load_classes(cfg)
    known = set(names)
    targets = set()
    if classes:
        for c in str(classes).split(","):
            c = c.strip()
            if not c:
                continue
            if c not in known:
                print(f"[label-queue] WARNING '{c}' is not a detector class -- ignored")
            else:
                targets.add(base_key(c))
    wpath, _ = _resolve_weights(cfg, weights)
    if wpath is None or not Path(wpath).exists():
        print("[label-queue] no detector weights -- train one first (tools/detect/train.py)")
        return
    from ultralytics import YOLO
    model = YOLO(str(wpath))
    # Decode with the WEIGHTS' own class list, not the current taxonomy -- see detect.model_class_names.
    from .detect import model_class_names
    pred_names = model_class_names(model) or names
    print(f"[label-queue] weights {wpath}")
    if pred_names != names:
        print(f"[label-queue] NOTE weights carry {len(pred_names)} classes vs {len(names)} in the"
              " current taxonomy -- decoded with the weights' names")

    # frames already in train/val are ANNOTATED; the rest of the queue is the real backlog
    done = {p.stem for s in ("train", "val") for p in (root / "images" / s).glob("*")
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    allq = [p for p in sorted(qdir.iterdir()) if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    pend = [p for p in allq if p.stem not in done]
    if limit:
        pend = pend[:int(limit)]
    print(f"[label-queue] {len(pend)} unlabelled of {len(allq)} queue frame(s)"
          f"{f'  (limited to {limit})' if limit else ''}")
    print(f"[label-queue] targets: {', '.join(sorted(targets)) if targets else 'ALL classes'}")

    # detect at a LOW floor: the whole point is to see what the model is unsure about, and the
    # live gate would hide exactly those boxes
    kw = {"conf": min(0.10, lo), "imgsz": 960, "verbose": False}
    if device:
        kw["device"] = device
    rows = []
    for i, p in enumerate(pend):
        try:
            r = model.predict(str(p), **kw)[0]
        except Exception:
            continue
        dets = [(float(b.conf[0]), base_key(pred_names[int(b.cls[0])]),
                 tuple(float(v) for v in b.xywhn[0].tolist())) for b in r.boxes]
        amb, unc, notes = _score_frame(dets, targets, lo, hi)
        if amb > 0 or unc > 0:
            rows.append((amb, unc, p, notes))
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(pend)}", flush=True)

    rows.sort(key=lambda r: (-(r[0] * 2 + r[1]), r[2].name))    # ambiguity counts double
    top = rows[:int(n)]
    print(f"\n[label-queue] {len(rows)} frame(s) scored above zero; showing the top {len(top)}\n")
    print(f"  {'amb':>5s} {'unc':>5s}  frame")
    for amb, unc, p, notes in top[:40]:
        note = ("  " + "; ".join(notes[:2])) if notes else ""
        print(f"  {amb:5.2f} {unc:5.2f}  {p.name}{note}")
    if len(top) > 40:
        print(f"  ... and {len(top)-40} more")

    out = root / "label_priority.txt"
    out.write_text("".join(f"{p.name}\n" for _a, _u, p, _n in top), encoding="utf-8")
    print(f"\n[label-queue] ranked list -> {out}")
    if copy and top:
        dst = root / "images" / "to_label_priority"
        dst.mkdir(parents=True, exist_ok=True)
        for _a, _u, p, _n in top:
            shutil.copy2(p, dst / p.name)
        print(f"[label-queue] copied {len(top)} frame(s) -> {dst}")
        print("[label-queue] point Label Studio Local Storage at THAT folder to label them first")
