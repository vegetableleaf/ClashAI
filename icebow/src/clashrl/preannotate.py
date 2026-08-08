"""Pre-annotate the unlabelled queue with the current detector, so you CORRECT boxes instead of DRAWING them.

`autolabel` can only box YOUR OWN troops -- it knows what you played and roughly where, so it
frame-diffs at the tap. It cannot touch the ENEMY, and enemy units are the whole labelling
backlog. This closes that gap the only way available without ground truth: run the detector we
already have over the queue and ship its boxes as PRE-ANNOTATIONS.

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

Output is a self-contained folder in the layout `label-studio-converter import yolo` expects
(classes.txt + images/ + labels/), which is the same converter `autolabel` already documents for
its own-troop boxes.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional


def preannotate(cfg, weights: Optional[str] = None, conf: float = 0.20,
                device: Optional[str] = None, limit: Optional[int] = None,
                out: Optional[str] = None, classes: Optional[str] = None) -> None:
    from .detect import _load_classes, _resolve_weights

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    qdir = root / "images" / cfg.get("detect", "label_queue_subdir", default="to_label")
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

    # Frames already in train/val are ANNOTATED -- never overwrite real human labels.
    done = {p.stem for s in ("train", "val") for p in (root / "images" / s).glob("*")
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    pend = [p for p in sorted(qdir.iterdir())
            if p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.stem not in done]
    if limit:
        pend = pend[:int(limit)]
    if not pend:
        print(f"[pre-annotate] nothing unlabelled in {qdir}")
        return

    dst = Path(out) if out else (root / "preannot")
    (dst / "images").mkdir(parents=True, exist_ok=True)
    (dst / "labels").mkdir(parents=True, exist_ok=True)
    (dst / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")

    from ultralytics import YOLO
    model = YOLO(str(wpath))
    print(f"[pre-annotate] weights {wpath}")
    print(f"[pre-annotate] {len(pend)} unlabelled frame(s) @ conf {conf} "
          f"(live gate is {cfg.get('observation', 'detector_conf', default=0.40)} -- lower on purpose)")

    kw = {"conf": float(conf), "imgsz": 960, "verbose": False}
    if device:
        kw["device"] = device

    hist: dict = {}
    n_box = n_img = 0
    for i, p in enumerate(pend):
        try:
            r = model.predict(str(p), **kw)[0]
        except Exception as exc:  # noqa: BLE001 -- one unreadable frame must not stop the run
            print(f"[pre-annotate] skipped {p.name}: {exc}")
            continue
        lines = []
        for b in r.boxes:
            cls = int(b.cls[0])
            if keep is not None and names[cls] not in keep:
                continue
            x, y, w, h = (float(v) for v in b.xywhn[0].tolist())
            lines.append(f"{cls} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
            hist[names[cls]] = hist.get(names[cls], 0) + 1
        shutil.copy2(p, dst / "images" / p.name)
        # An EMPTY .txt is meaningful: it says "detector found nothing here", which is a frame
        # worth a human eye rather than one to skip.
        (dst / "labels" / f"{p.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""),
                                                      encoding="utf-8")
        n_box += len(lines)
        n_img += 1
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(pend)}", flush=True)

    empty = n_img - sum(1 for f in (dst / "labels").glob("*.txt") if f.stat().st_size > 0)
    print(f"\n[pre-annotate] {n_img} frame(s), {n_box} pre-drawn box(es) "
          f"({n_box / max(1, n_img):.1f}/frame; {empty} frame(s) got nothing)")
    if hist:
        top = sorted(hist.items(), key=lambda kv: -kv[1])[:12]
        print("[pre-annotate] most-drawn: " + ", ".join(f"{k} {v}" for k, v in top))
    print(f"[pre-annotate] -> {dst}")
    print("[pre-annotate] NEXT:")
    print(f"  1) label-studio-converter import yolo -i {dst} -o {dst / 'tasks.json'}")
    print(f"  2) import tasks.json into Label Studio; point Local Storage at {dst / 'images'}")
    print(f"  3) paste {root / 'label_studio_config.xml'} as the labelling config")
    print("[pre-annotate] CORRECT every frame -- these are the CURRENT detector's guesses, so the "
          "units it misses are exactly the ones it needs taught. Accepting them unedited would "
          "train the next generation on its own output.")
