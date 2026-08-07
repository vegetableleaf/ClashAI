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
            ck = torch.load(p, map_location="cpu")
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
