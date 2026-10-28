"""P2-OPP1: freeze the live time split BEFORE any opponent training (plan1026 Pillar 2: train / calibration / sealed by
time; never train or tune on the sealed block). Writes live_split.json once; refuses to overwrite.

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/plan1026/opp/freeze_live_split.py FREEZE_TS

Blocks by the log stem's start time (live_play_YYYYMMDD_HHMMSS, local EDT):
  train        ts <  TRAIN_BEFORE (20261025_000000: everything before the CLXIII / CLXIV live era)
  calibration  TRAIN_BEFORE <= ts < FREEZE_TS (level A / strength calibration; never trained on)
  sealed       ts >= FREEZE_TS (every later match; level D only; never trained or tuned on)
Match filters (deck, account, trophies, frames) are applied by the row builder; the split is by time alone. The sha256 of
the train / calibration stem lists is recorded so the two blocks cannot change silently later.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
LOGS = ROOT / "scratchpad/gauntlet/L68/live_reader"
OUT = Path(__file__).with_name("live_split.json")
TRAIN_BEFORE = "20261025_000000"


def main():
    freeze = sys.argv[1]
    if not re.fullmatch(r"\d{8}_\d{6}", freeze) or freeze <= TRAIN_BEFORE:
        raise SystemExit("FREEZE_TS = YYYYMMDD_HHMMSS after " + TRAIN_BEFORE)
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: the split is frozen (never rewritten)")
    stems = sorted(p.stem[len("live_play_"):] for p in LOGS.glob("live_play_*.jsonl")
                   if re.fullmatch(r"live_play_\d{8}_\d{6}", p.stem))
    if stems and stems[-1] >= freeze:
        raise SystemExit(f"a log at/after the freeze already exists ({stems[-1]}): pick a later FREEZE_TS")
    train = [s for s in stems if s < TRAIN_BEFORE]
    cal = [s for s in stems if TRAIN_BEFORE <= s < freeze]
    h = lambda xs: hashlib.sha256("\n".join(xs).encode()).hexdigest()
    rec = {"frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "rule": __doc__.split("\n\n")[0].strip(),
           "train_before": TRAIN_BEFORE, "sealed_from": freeze,
           "blocks": {"train": {"logs": len(train), "first": train[0] if train else None, "last": train[-1] if train else None,
                                "stems_sha256": h(train)},
                      "calibration": {"logs": len(cal), "first": cal[0] if cal else None, "last": cal[-1] if cal else None,
                                      "stems_sha256": h(cal)},
                      "sealed": {"from": freeze, "logs_at_freeze": 0}},
           "note": "log counts are ALL live_play logs (any deck / account); the row builder filters matches"}
    OUT.write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
