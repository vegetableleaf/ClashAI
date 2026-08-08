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


def _detector_status(root: Path) -> Dict[str, Any]:
    """Trained weights, measured quality, labelled data, and what is still unlabelled."""
    det = root / "data" / "detect"
    runs = root / "runs" / "detect"
    weights = sorted(runs.glob("*/weights/best.pt"), key=lambda p: p.stat().st_mtime,
                     reverse=True) if runs.exists() else []
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
    return {
        "trained": bool(weights),
        "weights": str(weights[0]) if weights else None,
        "runs": [p.parent.parent.name for p in weights],
        "metrics": _last_metrics(weights[0].parent.parent) if weights else {},
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
