"""~15-minute device feasibility test: record ONE in-game replay with the memory reader and convert it. L74.

OWNER OK FIRST (it runs the read-only sampler on MuMu). Steps in NOTES.md "Device test"; in short:
  1. by hand: open a replay (TV Royale or the battle log) on MuMu; start it.
  2. icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/feasibility.py [--recording PATH]
     (--recording: skip the device and re-check an existing recording)
Prints the questions the test exists to answer: does the reader resolve a replay battle at all; are BOTH hands
visible (seat); does game_tick run faster than 20 ticks/s when the replay is sped up; applied_replay_tick vs
game_tick; plays per side and how many were positioned.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert as cv  # noqa: E402
import recorder as rc  # noqa: E402


def diagnose(path: Path) -> dict:
    ev = [json.loads(line) for line in open(path, encoding="utf-8")]
    fr = [e for e in ev if e.get("event") == "frame"]
    act = [e for e in fr if e["f"].get("battle_active") and e["f"].get("coherent")]
    stop = next((e for e in ev if e["event"] in ("battle_end", "refused")), {})
    out = dict(lines=len(fr), active=len(act), stop={k: v for k, v in stop.items() if k != "seats"},
               failures=sorted({e["f"].get("failure") for e in fr} - {None}))
    if len(act) >= 2:
        t = [(e["t_host"], int(e["f"]["game_tick"])) for e in act if int(e["f"]["game_tick"]) > 0]
        if len(t) >= 2 and t[-1][0] > t[0][0]:
            out["ticks_per_s"] = round((t[-1][1] - t[0][1]) / (t[-1][0] - t[0][0]), 2)   # 20 = real time
        out["seats"] = {s: sum(cv.seat(e["f"]) == s for e in act) for s in ("player", "spectator", "blind")}
        out["applied_replay_tick_minus_tick_first_last"] = [
            (e["f"].get("applied_replay_tick") or 0) - int(e["f"]["game_tick"]) for e in (act[0], act[-1])]
        out["entity_count_max"] = max(len(e["f"].get("entities") or ()) for e in act)
        out["projectiles_seen"] = sum(bool(e["f"].get("projectiles")) for e in act)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recording")
    ap.add_argument("--max-seconds", type=float, default=600.0)
    a = ap.parse_args()
    if a.recording:
        path = Path(a.recording)
    else:
        path = rc.OUT / f"rec_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        lines, stop = rc.device_lines()
        try:
            print("recording (no taps) -- play the replay now; Ctrl-C to abort", flush=True)
            print("stop:", rc.run(lines, path, a.max_seconds), flush=True)
        finally:
            stop()
    print(json.dumps(dict(recording=str(path), **diagnose(path)), indent=1))
    try:
        res = cv.convert(path)
    except SystemExit as e:
        print("CONVERT REFUSED / FAILED:", e)
        return 1
    out = path.with_name(path.stem + "_crawl")
    cv.write(res, out)
    sides = {s: [r for r in res["plays"] if r["attr_s"] == s] for s in ("red", "blue")}
    print(json.dumps(dict(out=str(out), mode=res["mode"], result=res["battle"]["result"],
                          decks=[res["battle"]["team_deck"], res["battle"]["opponent_deck"]],
                          plays={s: len(v) for s, v in sides.items()},
                          positioned={s: sum(r["located"] for r in v) for s, v in sides.items()}), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
