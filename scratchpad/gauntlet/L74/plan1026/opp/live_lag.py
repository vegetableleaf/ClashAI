"""P2-OPP step 3 input: on OUR seat, ticks from a decided play (`play` event) to its confirmed spawn (`confirmed` event, the
reader's first sighting of the new body) in the live logs of one live_split block -- the live tap -> sighting delay whose engine
part is crforge's 20-tick command delay (an opponent's act tick ~ its first sighting - (this delay - our tap time)).

    python -I live_lag.py [--block train] [--limit 200]

Reads only log NAMES in the block (the sealed block is never opened). Pairs each confirmation with the latest earlier play of
the same card within 80 ticks (o1_records' rule)."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
LOGS = ROOT / "scratchpad/gauntlet/L68/live_reader"
SPLIT = json.loads((Path(__file__).resolve().parent / "live_split.json").read_text())


def block_of(stem: str) -> str:
    s = stem[len("live_play_"):]
    return "train" if s < SPLIT["train_before"] else "sealed" if s >= SPLIT["sealed_from"] else "calibration"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", default="train", choices=("train", "calibration"))
    ap.add_argument("--limit", type=int, default=200, help="newest N logs of the block")
    a = ap.parse_args()
    names = sorted(p for p in LOGS.glob("live_play_*.jsonl") if block_of(p.stem) == a.block)[-a.limit:]
    d, lat, n_conf, n_pair = Counter(), [], 0, 0
    for p in names:
        plays, confs = [], []
        with open(p, "rb") as fh:
            for raw in fh:
                if raw.startswith(b'{"event": "play"'):
                    j = json.loads(raw)
                    plays.append((int(j["tick"]), j.get("name")))
                elif raw.startswith(b'{"event": "confirmed"'):
                    j = json.loads(raw)
                    confs.append((int(j.get("tick") or 0), j.get("name"), j.get("latency_s")))
        used = set()
        for t, nm, ls in confs:
            n_conf += 1
            c = [i for i, (tp, np_) in enumerate(plays) if i not in used and np_ == nm and 0 <= t - tp <= 80]
            if c:
                used.add(c[-1])
                d[t - plays[c[-1]][0]] += 1
                n_pair += 1
                if ls is not None:
                    lat.append(float(ls))
    xs = sorted(k for k, v in d.items() for _ in range(v))
    q = lambda f: xs[int(f * (len(xs) - 1))] if xs else None   # noqa: E731
    print(json.dumps({"block": a.block, "logs": len(names), "confirmations": n_conf, "paired": n_pair,
                      "ticks_play_to_confirm": {"p10": q(.1), "p25": q(.25), "p50": q(.5), "p75": q(.75), "p90": q(.9),
                                                "mean": round(sum(xs) / len(xs), 2) if xs else None},
                      "latency_s_median": sorted(lat)[len(lat) // 2] if lat else None,
                      "top": d.most_common(8)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
