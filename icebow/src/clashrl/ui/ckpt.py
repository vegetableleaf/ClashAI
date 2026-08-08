"""Inventory of the trained checkpoints under data/.

Reads only the metadata the trainers already store next to the weights (grid, deck,
n_cards, best benchmark win-rate, and -- for train-sim -- the match count at save
time). Weights are loaded to CPU, so listing never touches a running run's GPU
memory. Nothing here writes or deletes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

_CACHE: Dict[str, Dict[str, Any]] = {}          # path -> meta, keyed by (path, mtime, size)

# What each file in data/ IS. The names are the trainers' own fixed output paths, so the
# set is small and known -- but "policy.pt vs policy_sim.pt vs policy_sim_best.pt vs
# policy_rl.pt" says nothing on its own about which one to play or which is newer/better.
_ROLES = {
    "policy.pt": ("Imitation", "Learned from YOUR recordings (train-bc). Starting point, not "
                               "usually the one you play."),
    "policy_sim.pt": ("Simulator, latest", "Newest state of simulator training (train-sim). "
                                           "Overwritten as it trains -- not necessarily the best."),
    "policy_sim_best.pt": ("Simulator, best", "The best benchmark score simulator training ever "
                                              "reached. Usually the one to play."),
    "policy_sim_ppo.pt": ("Simulator PPO, latest", "Same idea as policy_sim.pt but from the PPO "
                                                   "trainer (train-sim-ppo), kept separate."),
    "policy_rl.pt": ("Live, latest", "Fine-tuned on real matches (train-rl). play uses this by "
                                     "default when it exists."),
    "policy_rl_prev.pt": ("Live, backup", "Automatic copy of policy_rl.pt from before the last "
                                          "train-rl run -- restore it if that run made things worse."),
}


def describe(name: str) -> Dict[str, Optional[str]]:
    """The role of a checkpoint file, or a best guess for an unknown name."""
    hit = _ROLES.get(name)
    if hit:
        return {"role": hit[0], "role_help": hit[1]}
    if name.startswith("policy_bench"):
        return {"role": "Benchmark scratch",
                "role_help": "Throwaway file written by sim-bench while measuring throughput. "
                             "Safe to delete; not something to play."}
    return {"role": None, "role_help": None}


def _read_meta(p: Path) -> Dict[str, Any]:
    key = f"{p}|{p.stat().st_mtime_ns}|{p.stat().st_size}"
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    meta: Dict[str, Any] = {}
    try:
        import torch
        try:
            ck = torch.load(p, map_location="cpu", weights_only=True)
        except Exception:                        # noqa: BLE001 -- older/plain pickles
            ck = torch.load(p, map_location="cpu", weights_only=False)
        if isinstance(ck, dict):
            for k in ("grid", "n_cards", "n_cells", "threat_dim", "deck", "best_wr",
                      "matches", "arena_size"):
                if k in ck:
                    v = ck[k]
                    meta[k] = v.tolist() if hasattr(v, "tolist") else v
            meta["heads"] = sorted(k for k in ck if k in ("model", "gate", "value"))
    except Exception as exc:                     # noqa: BLE001
        meta["error"] = str(exc)
    _CACHE.clear()                               # tiny inventory; keep only the freshest entries
    _CACHE[key] = meta
    return meta


def list_checkpoints(data_dir: Path, metrics_runs: Optional[List[Dict[str, Any]]] = None
                     ) -> List[Dict[str, Any]]:
    data_dir = Path(data_dir)
    out: List[Dict[str, Any]] = []
    if not data_dir.exists():
        return out
    for p in sorted(data_dir.glob("*.pt")):
        st = p.stat()
        meta = _read_meta(p)
        matches = meta.get("matches")
        if matches is None and metrics_runs:
            # older checkpoints predate the stored match count: fall back to the match
            # count of the run that was live when the file was last written.
            best = None
            for r in metrics_runs:
                if (r.get("start") or 0) <= st.st_mtime <= (r.get("end") or 0) + 120:
                    best = r
                    break
            if best:
                matches = best.get("matches")
        out.append({
            "name": p.name,
            "rel": f"data/{p.name}",
            "size": st.st_size,
            "mtime": st.st_mtime,
            **describe(p.name),
            "best_wr": meta.get("best_wr"),
            "matches": matches,
            "matches_estimated": meta.get("matches") is None and matches is not None,
            "grid": meta.get("grid"),
            "n_cards": meta.get("n_cards"),
            "deck": meta.get("deck"),
            "error": meta.get("error"),
        })
    out.sort(key=lambda c: c["mtime"], reverse=True)
    return out


# --- the two models, told apart -----------------------------------------------------
# This project trains TWO completely separate networks, and the flat data/*.pt listing
# hid that. They have different jobs, different training commands, different files, and
# one is useless without the other:
#   PLAYING AI  -- decides which card to play where. Trains in the simulator (no game
#                  needed) and optionally fine-tunes on live matches.
#   VISION AI   -- finds and names the units on the board in a screenshot. Trained from
#                  hand-labelled frames; without it the playing AI is blind to what the
#                  opponent has on the field.

def _last_metrics(run_dir: Path) -> Dict[str, Any]:
    """Final-epoch quality from Ultralytics' own results.csv.

    mAP50 is the headline: the share of units it finds AND names correctly at a loose
    overlap. 0 means it detects nothing usable -- which is the honest reading after
    training on a handful of boxes, and the number that has to be visible so a useless
    detector isn't mistaken for a working one just because the file exists.
    """
    csv = run_dir / "results.csv"
    if not csv.is_file():
        return {}
    try:
        lines = [ln for ln in csv.read_text(encoding="utf-8").splitlines() if ln.strip()]
        head, last = [c.strip() for c in lines[0].split(",")], lines[-1].split(",")
        row = dict(zip(head, last))
        pick = lambda k: (float(row[k]) if k in row and row[k] not in ("", "nan") else None)  # noqa: E731
        return {"epochs": pick("epoch"), "mAP50": pick("metrics/mAP50(B)"),
                "mAP50_95": pick("metrics/mAP50-95(B)"),
                "precision": pick("metrics/precision(B)"), "recall": pick("metrics/recall(B)")}
    except (OSError, ValueError, IndexError):
        return {}


# Ultralytics writes these next to every run. They are the only place you can SEE what the
# detector was fed and what it answered, which is what "is it learning anything" actually means.
_PREVIEWS = {
    "train_batch0.jpg": "A training batch with YOUR boxes drawn in -- what it is being taught.",
    "train_batch1.jpg": "Another training batch.",
    "train_batch2.jpg": "Another training batch.",
    "val_batch0_labels.jpg": "Validation frames with the true boxes.",
    "val_batch0_pred.jpg": "The same frames with what the detector PREDICTED. Empty here means "
                           "it currently finds nothing.",
    "labels.jpg": "How the labelled boxes are distributed over the classes and the board.",
    "results.png": "Ultralytics' own loss/metric curves for the whole run.",
    "confusion_matrix_normalized.png": "Which classes get mistaken for which.",
}


def _progress(run_dir: Path) -> Dict[str, Any]:
    """Per-epoch history of one run, plus whether it is still going.

    results.csv is appended after every epoch, so this doubles as the live view of a running
    training -- the panel had no way at all to show that something was happening.
    """
    csv = run_dir / "results.csv"
    if not csv.is_file():
        return {}
    try:
        lines = [ln for ln in csv.read_text(encoding="utf-8").splitlines() if ln.strip()]
        head = [c.strip() for c in lines[0].split(",")]
        rows = []
        for ln in lines[1:]:
            row = dict(zip(head, ln.split(",")))
            get = lambda k: (float(row[k]) if row.get(k) not in (None, "", "nan") else None)  # noqa: E731
            rows.append({"epoch": get("epoch"), "mAP50": get("metrics/mAP50(B)"),
                         "cls_loss": get("train/cls_loss"), "box_loss": get("train/box_loss")})
    except (OSError, ValueError, IndexError):
        return {}
    total = None
    args = run_dir / "args.yaml"
    if args.is_file():                       # epochs asked for, so "12 of 120" instead of "12"
        for ln in args.read_text(encoding="utf-8").splitlines():
            if ln.startswith("epochs:"):
                try:
                    total = int(ln.split(":", 1)[1].strip())
                except ValueError:
                    pass
                break
    import time as _t
    # Ultralytics writes results.png only when the run FINISHES, so its absence plus a
    # recently touched csv is a reliable "still going" -- freshness alone would keep calling
    # a run that ended two minutes ago live.
    running = (not (run_dir / "results.png").is_file()
               and (_t.time() - csv.stat().st_mtime) < 600)
    return {"rows": rows, "epochs_total": total, "running": running}


def _model_card(run_dir: Optional[Path]) -> Dict[str, Any]:
    """What the installed weights are, written by the trainer when a run FINISHES."""
    if run_dir is None:
        return {}
    p = run_dir / "model_card.json"
    if not p.is_file():
        return {}
    try:
        import json
        card = json.loads(p.read_text(encoding="utf-8"))
        return card if isinstance(card, dict) else {}
    except (OSError, ValueError):
        return {}


def _run_info(run_dir: Path) -> Dict[str, Any]:
    best = run_dir / "weights" / "best.pt"
    st = best.stat() if best.is_file() else None
    csv = run_dir / "results.csv"
    # results.csv is touched every epoch, best.pt only when the score improves: take the later
    # of the two so a long run that stopped improving still sorts as the most recent activity.
    mtime = max([t for t in (st.st_mtime if st else None,
                             csv.stat().st_mtime if csv.is_file() else None) if t]
                or [run_dir.stat().st_mtime])
    return {
        "name": run_dir.name,
        "rel": f"runs/detect/{run_dir.name}/weights/best.pt",
        "mtime": mtime,
        "size": st.st_size if st else None,
        "has_weights": bool(st),
        "metrics": _last_metrics(run_dir),
        "previews": [f for f in _PREVIEWS if (run_dir / f).is_file()],
    }


VISION_RUN = "vision"           # mirrors detect.VISION_RUN / tools/detect/train.py RUN_NAME


def _detector_status(root: Path) -> Dict[str, Any]:
    """THE vision model: one folder, one best.pt, one score.

    There used to be a run per training (board, board-2, board-3 ...) and whatever trained
    last quietly became the operating detector; then a config pin, which just moved the
    question. There is now exactly one, at runs/detect/vision, and a retrain replaces it.
    Nothing selects and nothing can be selected.
    """
    det = root / "data" / "detect"
    runs = root / "runs" / "detect"
    n = lambda p, pat="*": len(list(p.glob(pat))) if p.exists() else 0    # noqa: E731
    classes = det / "classes.txt"
    # boxes actually drawn -- an empty label file is legal YOLO ("nothing here") but a set
    # that is empty by accident trains the detector to predict nothing at all.
    boxes = with_boxes = 0
    for split in ("train", "val"):
        d = det / "labels" / split
        if not d.is_dir():
            continue
        for p in d.glob("*.txt"):
            k = len([ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()])
            boxes += k
            with_boxes += bool(k)
    # Mirrors _resolve_weights() in detect.py: an explicit pin wins, otherwise THE vision model.
    home = runs / VISION_RUN
    active_dir = (home if (home / "weights" / "best.pt").is_file()
                  or (home / "results.csv").is_file() else None)
    # Anything left over from when every training made its own folder. Not models -- clutter.
    strays = sorted(d.name for d in (runs.iterdir() if runs.is_dir() else [])
                    if d.is_dir() and d.name != VISION_RUN
                    and (d / "weights" / "best.pt").is_file())
    info = _run_info(active_dir) if active_dir else {}
    return {
        "trained": bool(active_dir and (active_dir / "weights" / "best.pt").is_file()),
        "weights": str(active_dir / "weights" / "best.pt") if active_dir else None,
        "run": active_dir.name if active_dir else None,
        "rel": f"runs/detect/{active_dir.name}/weights/best.pt" if active_dir else None,
        "mtime": info.get("mtime"),
        "size": info.get("size"),
        "strays": strays,
        # The CARD describes the weights on disk; results.csv describes whatever is training
        # now (and is truncated the moment a new run starts). Prefer the card.
        "metrics": _model_card(active_dir) or (_last_metrics(active_dir) if active_dir else {}),
        "metrics_from": ("card" if _model_card(active_dir) else "results.csv") if active_dir else None,
        "progress": _progress(active_dir) if active_dir else {},
        "previews": _PREVIEWS,
        "preview_files": info.get("previews", []),
        "labelled_train": n(det / "images" / "train"),
        "labelled_val": n(det / "images" / "val"),
        "to_label": n(det / "images" / "to_label"),
        "boxes": boxes,
        "frames_with_boxes": with_boxes,
        "classes": len(classes.read_text(encoding="utf-8").split()) if classes.exists() else 0,
        "runs_dir": str(runs),
        "to_label_dir": str(det / "images" / "to_label"),
    }


def models(root: Path, metrics_runs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Both networks, each with ONE headline entry plus its variants.

    The headline for the playing AI is the file `play` would actually load with no --init,
    because that is the question the list has to answer -- not which file is newest.
    """
    cks = list_checkpoints(root / "data", metrics_runs)
    by_name = {c["name"]: c for c in cks}
    # play's own order: data/policy_rl.pt when present, else train.checkpoint (policy.pt).
    # policy_sim_best.pt is usually the strongest thing available, so surface it as the
    # suggestion when it exists and nothing has been fine-tuned live yet.
    main = by_name.get("policy_rl.pt") or by_name.get("policy.pt")
    suggest = by_name.get("policy_sim_best.pt")
    return {
        "policy": {
            "main": main,
            "suggested": suggest if (suggest and suggest is not main) else None,
            "all": cks,
        },
        "vision": _detector_status(root),
    }
