"""Pre-annotate the unlabelled queue with the current detector, so you CORRECT boxes instead of DRAWING them.

`autolabel` can only box YOUR OWN troops -- it knows what you played and roughly where, so it
frame-diffs at the tap. It cannot touch the ENEMY, and enemy units are the whole labelling
backlog. This closes that gap the only way available without ground truth: run the detector we
already have over the queue and ship its boxes as PRE-ANNOTATIONS.

NO IMAGES ARE COPIED
--------------------
Label Studio serves this project from `data/detect/images`, so a source storage must live UNDER
that folder -- and the frames already do, in `images/to_label`. Copying them into a bundle would
duplicate thousands of files, put them outside the LS root where they cannot be served, and leave
a second copy to drift. So this writes only a TASKS FILE pointing at the frames where they already
are, using the same reference form LS itself produces:

    /data/local-files/?d=to_label\\trl_....jpg

`detect-import` matches an export back to disk by BASENAME (see `_ls_export_image_name`), so the
labels come home regardless of which folder LS served them from.

WHY A LOWER THRESHOLD THAN PLAY
-------------------------------
`observation.detector_conf` is 0.40 because a phantom detection costs the policy a bad decision.
Labelling has the opposite economics: deleting a wrong box is one keypress, drawing a missed one
takes seconds and a zoom. So pre-annotation is RECALL-FIRST -- the default gate here is 0.20, far
below the live gate, deliberately over-producing boxes.

THIS IS A BOOTSTRAP, NOT TRUTH
------------------------------
The detector it uses is the one being improved (board-16: 0.72 whitelist recall), so it will miss
units and mislabel lookalikes -- exactly the cases that most need labelling. Accepting its output
uncorrected would train the next generation on its own predictions and freeze those blind spots
in. Every frame still needs a human pass; what this removes is the DRAWING, not the CHECKING.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _ls_ref(subdir: str, name: str) -> str:
    """The task image reference, in the form this project's LS instance already emits."""
    rel = f"{subdir}\\{name}" if subdir else name
    return "/data/local-files/?d=" + rel


def preannotate(cfg, weights: Optional[str] = None, conf: float = 0.20,
                device: Optional[str] = None, limit: Optional[int] = None,
                out: Optional[str] = None, classes: Optional[str] = None,
                subdir: Optional[str] = None, model_version: Optional[str] = None) -> None:
    from .detect import _load_classes, _resolve_weights, model_class_names

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    qsub = subdir if subdir is not None else cfg.get("detect", "label_queue_subdir",
                                                     default="to_label")
    qdir = root / "images" / qsub
    if not qdir.is_dir():
        print(f"[pre-annotate] no queue folder at {qdir}")
        return

    names = _load_classes(cfg)
    keep = None
    if classes:
        keep = {c.strip() for c in str(classes).split(",") if c.strip()}
        unknown = keep - set(names)
        if unknown:
            print(f"[pre-annotate] WARNING not detector classes, ignored: {', '.join(sorted(unknown))}")
        keep &= set(names)

    wpath, _ = _resolve_weights(cfg, weights)
    if wpath is None or not Path(wpath).exists():
        print("[pre-annotate] no detector weights -- train one first (tools/detect/train.py)")
        return

    # Frames already in train/val are ANNOTATED -- never re-offer them.
    done = {p.stem for s in ("train", "val") for p in (root / "images" / s).glob("*")
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    pend = [p for p in sorted(qdir.iterdir())
            if p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.stem not in done]
    if limit:
        pend = pend[:int(limit)]
    if not pend:
        print(f"[pre-annotate] nothing unlabelled in {qdir}")
        return

    from ultralytics import YOLO
    model = YOLO(str(wpath))
    # A checkpoint's class INDICES are frozen at training time, so decode with the WEIGHTS' names
    # and match to the current taxonomy BY NAME -- see detect.model_class_names.
    pred_names = model_class_names(model)
    current = set(names)
    dropped = [n for n in pred_names if n not in current]
    mv = model_version or Path(wpath).parent.parent.name          # e.g. 'board-16'
    print(f"[pre-annotate] weights {wpath}  (model_version '{mv}')")
    if dropped:
        print(f"[pre-annotate] weights carry {len(pred_names)} classes vs {len(names)} current; "
              f"{len(dropped)} retired and skipped: {', '.join(sorted(dropped)[:6])}"
              + (" ..." if len(dropped) > 6 else ""))
    print(f"[pre-annotate] {len(pend)} unlabelled frame(s) in images/{qsub} @ conf {conf} "
          f"(live gate is {cfg.get('observation', 'detector_conf', default=0.40)} -- lower on purpose)")

    kw = {"conf": float(conf), "imgsz": 960, "verbose": False}
    if device:
        kw["device"] = device

    tasks, hist = [], {}
    n_box = n_skip = empty = 0
    for i, p in enumerate(pend):
        try:
            r = model.predict(str(p), **kw)[0]
        except Exception as exc:  # noqa: BLE001 -- one unreadable frame must not stop the run
            print(f"[pre-annotate] skipped {p.name}: {exc}")
            continue
        ih, iw = (int(v) for v in r.orig_shape[:2])
        regions = []
        for b in r.boxes:
            nm = pred_names[int(b.cls[0])]
            if nm not in current:
                n_skip += 1
                continue
            if keep is not None and nm not in keep:
                continue
            cx, cy, bw, bh = (float(v) for v in b.xywhn[0].tolist())
            # LS rectangles are PERCENTAGES of the image with a TOP-LEFT origin; YOLO is a
            # normalised CENTRE. Getting this wrong shifts every box by half its own size.
            x = max(0.0, min(100.0, (cx - bw / 2) * 100.0))
            y = max(0.0, min(100.0, (cy - bh / 2) * 100.0))
            regions.append({
                "from_name": "label", "to_name": "image", "type": "rectanglelabels",
                "original_width": iw, "original_height": ih, "image_rotation": 0,
                "value": {"x": x, "y": y,
                          "width": max(0.0, min(100.0 - x, bw * 100.0)),
                          "height": max(0.0, min(100.0 - y, bh * 100.0)),
                          "rotation": 0, "rectanglelabels": [nm]},
                "score": float(b.conf[0]),
            })
            hist[nm] = hist.get(nm, 0) + 1
        n_box += len(regions)
        if not regions:
            empty += 1
        # A task with an EMPTY prediction is still emitted: "the detector found nothing here" is a
        # frame worth a human eye, not one to hide.
        tasks.append({"data": {"image": _ls_ref(qsub, p.name)},
                      "predictions": [{"model_version": mv, "result": regions}]})
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(pend)}", flush=True)

    dst = Path(out) if out else (root / "preannot_tasks.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(tasks, indent=1), encoding="utf-8")

    print(f"\n[pre-annotate] {len(tasks)} task(s), {n_box} pre-drawn box(es) "
          f"({n_box / max(1, len(tasks)):.1f}/frame; {empty} frame(s) got nothing)")
    if n_skip:
        print(f"[pre-annotate] {n_skip} detection(s) dropped as retired classes")
    if hist:
        top = sorted(hist.items(), key=lambda kv: -kv[1])[:12]
        print("[pre-annotate] most-drawn: " + ", ".join(f"{k} {v}" for k, v in top))
    print(f"[pre-annotate] -> {dst}  (NO images copied -- tasks point into images/{qsub})")
    print("[pre-annotate] NEXT:")
    print(f"  1) NEW Label Studio project; labelling config = {root / 'label_studio_config.xml'}")
    print("  2) add Local Storage pointing at data/detect/images as usual, but do NOT press Sync "
          "-- syncing would create a SECOND, prediction-less task per frame")
    print(f"  3) Import {dst.name}; the predictions come with it")
    print("[pre-annotate] CORRECT every frame -- these are the CURRENT detector's guesses, so the "
          "units it misses are exactly the ones it needs taught. Accepting them unedited would "
          "train the next generation on its own output.")
