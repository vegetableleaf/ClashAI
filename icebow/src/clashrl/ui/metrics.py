"""Parse training progress out of the CLI's stdout and persist it.

The training commands already print everything the dashboard needs; scraping those
lines keeps the trainers untouched (no metrics hooks to keep in sync) and works for
runs started outside the UI too, if their log is replayed through `parse_line`.

Records land in `data/metrics.jsonl`, one JSON object per line, so a restart of the
UI (or of the machine) does not lose the curve. The file is append-only -- nothing
under data/ is ever rewritten or deleted here.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_LOCK = threading.Lock()

# "[train-sim] 250 matches: winrate=  44% avg_rew=+1.2 eps=0.94 replay=1200 3.4 m/s
#  total 110W-140L-0D loss=0.123"                (train-sim-ppo prints pl/vl/ent/clip instead of loss)
_PROGRESS = re.compile(r"^\[(?P<cmd>train-sim|train-sim-ppo)\]\s+(?P<matches>\d+)\s+matches:")
# "[train-sim] EVAL @ 500: ladder(L13-16)  72% (avg-3  70%) | fair(L13)  55% (avg-3  54%) | ..."
_EVAL = re.compile(
    r"^\[(?P<cmd>train-sim|train-sim-ppo)\]\s+EVAL\s+@\s+(?P<matches>\d+):\s+"
    r"ladder\((?P<ladder_lbl>[^)]*)\)\s*(?P<ladder>[\d.]+)%\s*\(avg-(?P<n>\d+)\s*(?P<ladder_avg>[\d.]+)%\)"
)
_EVAL_FAIR = re.compile(r"fair\((?P<fair_lbl>[^)]*)\)\s*(?P<fair>[\d.]+)%\s*\(avg-\d+\s*(?P<fair_avg>[\d.]+)%\)")
_BEST = re.compile(r"^\[(?P<cmd>train-sim|train-sim-ppo)\]\s+new BEST ladder avg\s*(?P<best>[\d.]+)%")
# "[train-bc] it 2/3 epoch 5/10  loss 1.234  card_acc 0.55  cell_acc 0.12"
_BC_EPOCH = re.compile(
    r"^\[train-bc\]\s+(?:it\s+(?P<it>\d+)/(?P<iters>\d+)\s+)?epoch\s+(?P<epoch>\d+)/(?P<epochs>\d+)\s+"
    r"loss\s+(?P<loss>[\d.]+)\s+card_acc\s+(?P<card_acc>[\d.]+)\s+cell_acc\s+(?P<cell_acc>[\d.]+)"
)
# "[train-rl] match 12: win crowns=2-1 reward=+3.4 plays=18 eps=0.09 replay=900 loss=0.2  record 7W-5L"
_RL_MATCH = re.compile(
    r"^\[train-rl\]\s+match\s+(?P<match>\d+):\s+(?P<outcome>win|loss|draw|unknown)\b"
)

_KV = re.compile(r"([a-z_]+)=\s*([+-]?\d+(?:\.\d+)?)")
_MPS = re.compile(r"([\d.]+)\s+m/s")
_WLD = re.compile(r"\b(\d+)W-(\d+)L(?:-(\d+)D)?\b")


def parse_line(line: str) -> Optional[Dict[str, Any]]:
    """Turn one stdout line into a metric record, or None if it carries no numbers."""
    line = line.rstrip()

    m = _PROGRESS.match(line)
    if m:
        rec: Dict[str, Any] = {"kind": "progress", "cmd": m.group("cmd"),
                               "matches": int(m.group("matches"))}
        for k, v in _KV.findall(line):
            if k in ("winrate", "avg_rew", "eps", "replay", "loss", "pl", "vl", "ent", "clip"):
                rec[k] = float(v)
        mm = _MPS.search(line)
        if mm:
            rec["mps"] = float(mm.group(1))
        wld = _WLD.search(line)
        if wld:
            rec["w"], rec["l"] = int(wld.group(1)), int(wld.group(2))
            rec["d"] = int(wld.group(3) or 0)
        return rec

    m = _EVAL.match(line)
    if m:
        rec = {"kind": "eval", "cmd": m.group("cmd"), "matches": int(m.group("matches")),
               "ladder_lbl": m.group("ladder_lbl"), "ladder": float(m.group("ladder")),
               "ladder_avg": float(m.group("ladder_avg")), "avg_n": int(m.group("n"))}
        f = _EVAL_FAIR.search(line)
        if f:
            rec["fair_lbl"] = f.group("fair_lbl")
            rec["fair"] = float(f.group("fair"))
            rec["fair_avg"] = float(f.group("fair_avg"))
        return rec

    m = _BEST.match(line)
    if m:
        return {"kind": "best", "cmd": m.group("cmd"), "best": float(m.group("best"))}

    m = _BC_EPOCH.match(line)
    if m:
        g = m.groupdict()
        return {"kind": "epoch", "cmd": "train-bc",
                "it": int(g["it"] or 1), "iters": int(g["iters"] or 1),
                "epoch": int(g["epoch"]), "epochs": int(g["epochs"]),
                "loss": float(g["loss"]), "card_acc": float(g["card_acc"]),
                "cell_acc": float(g["cell_acc"])}

    m = _RL_MATCH.match(line)
    if m:
        rec = {"kind": "match", "cmd": "train-rl", "matches": int(m.group("match")),
               "outcome": m.group("outcome")}
        for k, v in _KV.findall(line):
            if k in ("reward", "plays", "eps", "replay", "loss"):
                rec[k] = float(v)
        wld = _WLD.search(line)
        if wld:
            rec["w"], rec["l"] = int(wld.group(1)), int(wld.group(2))
            rec["d"] = int(wld.group(3) or 0)
        return rec

    return None


class MetricsStore:
    """Append-only JSONL sink + reader for the dashboard."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, rec: Dict[str, Any]) -> None:
        rec = dict(rec)
        rec.setdefault("t", time.time())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def read(self, run: Optional[str] = None, limit: int = 6000) -> List[Dict[str, Any]]:
        """Records for one run (or all), newest-truncated to `limit`."""
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue                                # a torn line from a hard kill: skip it
                if run and rec.get("run") != run:
                    continue
                out.append(rec)
        return out[-limit:]

    def runs(self) -> List[Dict[str, Any]]:
        """One summary row per recorded run, newest first."""
        agg: Dict[str, Dict[str, Any]] = {}
        for rec in self.read(limit=10 ** 9):
            rid = rec.get("run")
            if not rid:
                continue
            a = agg.setdefault(rid, {"run": rid, "cmd": rec.get("cmd"), "start": rec.get("t"),
                                     "end": rec.get("t"), "matches": 0, "records": 0,
                                     "target": None, "best": None, "argv": None,
                                     "has_data": False})
            a["records"] += 1
            if rec.get("kind") in ("progress", "eval", "epoch", "match", "best"):
                a["has_data"] = True
            a["end"] = rec.get("t", a["end"])
            if rec.get("cmd"):
                a["cmd"] = rec["cmd"]
            if rec.get("kind") == "run_start":
                a["argv"] = rec.get("argv")
                a["target"] = rec.get("target_matches")
                a["start"] = rec.get("t", a["start"])
            if isinstance(rec.get("matches"), int):
                a["matches"] = max(a["matches"], rec["matches"])
            if rec.get("kind") == "eval" and rec.get("ladder_avg") is not None:
                a["best"] = max(a["best"] or 0.0, float(rec["ladder_avg"]))
        # a run that never produced a single metric line (crashed at import, or a command
        # that simply doesn't report numbers) would only clutter the run picker.
        return sorted((a for a in agg.values() if a["has_data"]),
                      key=lambda r: r.get("start") or 0, reverse=True)


def to_csv(records: Iterable[Dict[str, Any]]) -> str:
    """Flatten records to CSV (union of all keys) -- the 'Reporting als Tabelle' export."""
    records = list(records)
    if not records:
        return "t\n"
    cols: List[str] = []
    for r in records:
        for k in r:
            if k not in cols:
                cols.append(k)
    head = ["t", "run", "cmd", "kind"]
    cols = head + [c for c in cols if c not in head]
    rows = [";".join(cols)]
    for r in records:
        rows.append(";".join(_csv_cell(r.get(c)) for c in cols))
    return "\n".join(rows) + "\n"


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    if any(c in s for c in ';"\n'):
        return '"' + s.replace('"', '""') + '"'
    return s
