"""Pack the vision AI into one .zip, and unpack one back in.

Two machines, two people, one detector: labelling is the expensive part of this project and
it is the part that combines cleanly (a Musketeer looks the same in everyone's client, unlike
the playing AI whose weights are bound to one deck). So the model and the labelled frames
have to be movable in one file, without git, without a server, without anyone typing a path.

Two bundle kinds, because they answer different questions:

    model    the weights plus what they measure at -- ~20 MB, "give me your detector"
    full     the weights AND the labelled dataset -- larger, "let me keep training yours"

Both carry a `manifest.json` so an import can say what it is about to do BEFORE doing it,
and both are validated against this checkout's class list: a bundle whose classes.txt does
not match ours would silently relabel every box (measured here once already -- a stale
236-entry list against a 225-entry one trained Mini P.E.K.K.A as Minion).

Nothing here reaches the network. It writes a file; you move it however you like.
"""
from __future__ import annotations

import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

MANIFEST = "manifest.json"
VISION_RUN = "vision"
_MODEL_FILES = ("weights/best.pt", "model_card.json", "results.csv", "args.yaml")


def _run_dir(root: Path) -> Path:
    return root / "runs" / "detect" / VISION_RUN


def _classes(root: Path) -> List[str]:
    p = root / "config" / "detect_classes.yaml"
    if not p.is_file():
        return []
    import yaml
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return [str(c) for c in (data.get("classes") or [])]


def _label_stats(root: Path) -> Dict[str, int]:
    det = root / "data" / "detect"
    frames = boxes = 0
    for split in ("train", "val"):
        d = det / "labels" / split
        if not d.is_dir():
            continue
        for p in d.glob("*.txt"):
            n = len([ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()])
            frames += 1
            boxes += n
    return {"label_files": frames, "boxes": boxes}


def describe(root: Path) -> Dict[str, Any]:
    """What an export would contain right now -- shown before the download starts."""
    run = _run_dir(root)
    card = {}
    cp = run / "model_card.json"
    if cp.is_file():
        try:
            card = json.loads(cp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            card = {}
    weights = run / "weights" / "best.pt"
    det = root / "data" / "detect"
    n_img = sum(len(list((det / "images" / s).glob("*.jpg")))
                for s in ("train", "val") if (det / "images" / s).is_dir())
    return {
        "trained": weights.is_file(),
        "weights_size": weights.stat().st_size if weights.is_file() else 0,
        "metrics": {k: card.get(k) for k in ("mAP50", "precision", "recall", "epochs",
                                             "model", "imgsz", "trained_on_boxes")},
        "classes": len(_classes(root)),
        "images": n_img,
        **_label_stats(root),
    }


def export(root: Path, out: Path, kind: str = "model") -> Dict[str, Any]:
    """Write a bundle. `kind` is 'model' (weights only) or 'full' (weights + labelled data)."""
    if kind not in ("model", "full"):
        raise ValueError(f"unknown bundle kind: {kind!r}")
    run, det = _run_dir(root), root / "data" / "detect"
    if not (run / "weights" / "best.pt").is_file():
        raise FileNotFoundError("no trained vision model to export "
                                f"({run / 'weights' / 'best.pt'} does not exist)")
    info = describe(root)
    manifest = {
        "bundle": "clashai-vision", "version": 1, "kind": kind,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "classes": _classes(root), "model": info["metrics"],
        "counts": {k: info[k] for k in ("images", "label_files", "boxes")},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST, json.dumps(manifest, indent=1))
        for rel in _MODEL_FILES:
            p = run / rel
            if p.is_file():
                z.write(p, f"model/{rel}"); n += 1
        if kind == "full":
            for split in ("train", "val"):
                for sub in ("images", "labels"):
                    d = det / sub / split
                    if not d.is_dir():
                        continue
                    for p in sorted(d.iterdir()):
                        if p.is_file():
                            z.write(p, f"dataset/{sub}/{split}/{p.name}"); n += 1
    return {"path": str(out), "size": out.stat().st_size, "files": n, "manifest": manifest}


def inspect(bundle: Path) -> Dict[str, Any]:
    """Read a bundle's manifest without unpacking anything."""
    with zipfile.ZipFile(bundle) as z:
        try:
            m = json.loads(z.read(MANIFEST).decode("utf-8"))
        except KeyError:
            raise ValueError("not a ClashAI vision bundle (no manifest.json)") from None
        names = z.namelist()
    if m.get("bundle") != "clashai-vision":
        raise ValueError(f"not a ClashAI vision bundle ({m.get('bundle')!r})")
    m["has_model"] = any(n.startswith("model/weights/") for n in names)
    m["dataset_files"] = sum(1 for n in names if n.startswith("dataset/"))
    return m


def import_(root: Path, bundle: Path, take_model: bool = True, take_dataset: bool = True,
            backup_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Install a bundle. The existing model is copied aside first, never just overwritten.

    Dataset frames are merged, not replaced: a file that already exists here is SKIPPED, so
    importing someone else's labels can only add to yours. Same-named frames from two people
    are almost certainly the same frame, and taking theirs would silently discard your work.
    """
    m = inspect(bundle)
    theirs, ours = m.get("classes") or [], _classes(root)
    if theirs and ours and theirs != ours:
        raise ValueError(
            f"class lists differ ({len(theirs)} vs {len(ours)} entries) -- importing would "
            "relabel every box, because a label file stores a class NUMBER, not a name. "
            "Line the taxonomies up first.")
    run, det = _run_dir(root), root / "data" / "detect"
    added = skipped = 0
    replaced_backup = None
    with zipfile.ZipFile(bundle) as z:
        names = z.namelist()
        if take_model and any(n.startswith("model/weights/") for n in names):
            if (run / "weights" / "best.pt").is_file() and backup_dir:
                backup_dir.mkdir(parents=True, exist_ok=True)
                replaced_backup = backup_dir / f"vision_{time.strftime('%Y%m%d-%H%M%S')}.zip"
                export(root, replaced_backup, "model")
            for n in names:
                if not n.startswith("model/"):
                    continue
                target = run / n[len("model/"):]
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                added += 1
        if take_dataset:
            for n in names:
                if not n.startswith("dataset/") or n.endswith("/"):
                    continue
                target = det / n[len("dataset/"):]
                if target.exists():
                    skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                added += 1
    return {"manifest": m, "added": added, "skipped_existing": skipped,
            "previous_model_saved_to": str(replaced_backup) if replaced_backup else None}
