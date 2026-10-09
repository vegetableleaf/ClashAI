"""L74 latency2: the live decision -> confirmation chain, per stage, from existing live_play logs (read-only, no device),
and the decision -> decision gap a planned follow-up can reach.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency2/stage_chain.py [glob ...] > stage_chain.txt

Deployed input path = --fast-input --tap-gap-ms 0 (start event). Per confirmed play (tap_timing + confirmed events):
  sample_age   device sample of the decision frame -> decide() start        (tap_timing.sample_age_ms)
  decide       decide() wall time                                           (decide_ms)
  tap          hand tap + board tap through the persistent shell            (tap_ms)
  tap_end      device sample -> board tap returned                          (tap_end_ms)
  game         board tap returned -> the hand slot rotated = the game's own delay    ((T_rot - T0) * 50 - tap_end)
  lock tail    2 ticks by construction: the pending lock ends on the frame AFTER the confirmation frame
Follow-up (planned second tap, no model call): it can go out as soon as the first board tap has returned AND the first
frame with tick >= T0 + after has been processed. Frames are 2 ticks apart and arrive ~sample + transport, so
  fire_ms(after) = max(tap_end, (ceil(after / 2) * 2) * 50 + frame_transport)    measured from the decision frame's sample
  deploy gap ~ fire gap + the second tap's own duration - the first tap's remaining time (<= tap_ms)
"""
from __future__ import annotations

import glob
import json
import math
import statistics as st
import sys
from pathlib import Path

MAIN_LOGS = Path(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader")


def q(v, ps=(5, 25, 50, 75, 95)):
    v = sorted(v)
    if not v:
        return "n=0"
    pick = lambda p: v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]
    return f"n={len(v)} mean={st.mean(v):.1f} " + " ".join(f"p{p}={pick(p):g}" for p in ps)


def rows_of(path: Path):
    """-> list of per-play dicts for a log of the deployed configuration (fast_input, tap_gap_ms 0), else []."""
    cfg, plays, cur, out = None, [], None, []
    for ln in path.open(encoding="utf-8"):
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ev = e.get("event")
        if ev == "start":
            cfg = (bool(e.get("fast_input")), e.get("tap_gap_ms", 50))
        elif ev == "play":
            cur = dict(T0=e["tick"], name=e.get("name"), elixir=e.get("elixir"))
            plays.append(cur)
        elif ev == "tap_timing" and cur is not None and e["tick"] == cur["T0"] and "tap_end_ms" in e:
            cur.update(decide=e["decide_ms"], tap=e["tap_ms"], sample_age=e["sample_age_ms"], tap_end=e["tap_end_ms"],
                       fast=e.get("fast_input"))
        elif ev == "confirmed" and cur is not None and "T_rot" not in cur and e.get("name") == cur["name"]:
            cur["T_rot"] = e["tick"]
    return cfg, [p for p in plays if "T_rot" in p and "tap_end" in p]


def main() -> None:
    pats = sys.argv[1:] or [str(MAIN_LOGS / "live_play_20261008_*.jsonl"), str(MAIN_LOGS / "live_play_20261009_*.jsonl")]
    files = sorted({f for pat in pats for f in glob.glob(pat)})
    deployed, other = [], []
    for f in files:
        cfg, rows = rows_of(Path(f))
        (deployed if cfg == (True, 0) else other).extend(rows)
    print(f"logs {len(files)}; plays with stage timings: deployed config (fast-input, gap 0) {len(deployed)}, other {len(other)}")
    r = deployed
    print("\n== deployed input path, per confirmed play ==")
    print(f"sample_age ms      {q([x['sample_age'] for x in r])}")
    print(f"decide ms          {q([x['decide'] for x in r])}")
    print(f"tap ms             {q([x['tap'] for x in r])}")
    print(f"tap_end ms         {q([x['tap_end'] for x in r])}   (sample -> board tap returned; = ticks x 50)")
    game = [(x["T_rot"] - x["T0"]) * 50 - x["tap_end"] for x in r]
    print(f"game ms            {q(game)}   (board tap returned -> slot rotated)")
    print(f"decision->confirm ticks {q([x['T_rot'] - x['T0'] for x in r])}")
    share = [(x["tap_end"]) / ((x["T_rot"] - x["T0"]) * 50) for x in r]
    print(f"our share of decision->confirm: median {st.median(share):.1%}; game share {1 - st.median(share):.1%}")
    print("lock tail (confirmation frame -> next decision): 2 ticks by construction (the confirmation frame never decides)")
    # follow-up reachable gap
    print("\n== planned follow-up: wall ms from the first decision frame's sample to the second tap going out ==")
    transport = 5.0          # frame delivery after its sample (recv_age / lag): p50 1 ms, p95 ~8 ms in fast mode
    for after in (0, 2, 4, 6, 10):
        frame_ms = math.ceil(after / 2) * 2 * 50 + transport if after else 0
        fire = [max(x["tap_end"], frame_ms) for x in r]
        ticks = [f / 50 for f in fire]
        print(f"  after_ticks={after:>2}: fire at {q([round(t, 2) for t in ticks])} ticks")
    gap_deploy = [x["tap"] / 50 for x in r]
    print(f"  the second board tap lands ~its own tap_ms after the first returned: +{q([round(g, 2) for g in gap_deploy])} "
          f"ticks, so landing-to-landing gap ~ fire gap(after<=2) - first tap's arrival lead + that (ticks, estimate)")
    print("\n== for comparison: default input path (adb.exe per tap, gap 50) ==")
    o = [x for x in other if not x.get("fast")]
    if o:
        print(f"tap_end ms {q([x['tap_end'] for x in o])};  decision->confirm ticks {q([x['T_rot'] - x['T0'] for x in o])}")


if __name__ == "__main__":
    main()
