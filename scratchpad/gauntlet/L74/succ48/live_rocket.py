"""succ48 (owner 10-25): live Rocket / Tornado / combo tally for one live checkpoint.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/succ48/live_rocket.py [CKPT_SUBSTRING]   (default CLXIII)

Reads scratchpad/gauntlet/L68/live_reader/live_play_*.jsonl whose start event's ckpt contains the substring. Per match:
accepted plays (event "play"), a COMBO = a Rocket and our Tornado within COMBO_TICKS of each other, a RULE combo = a decision
whose "why" names rocket_tornado (the live --rocket-tornado rule). Prints totals and per-match rates."""
import glob
import json
import sys
from pathlib import Path

LOGS = Path(__file__).resolve().parents[2] / "L68" / "live_reader"
COMBO_TICKS = 60          # 3 s (rocket_slices S5 uses -24..+40 ticks around the Rocket; 3 s either side is looser)


def match(f, key):
    plays, rule, ok = [], 0, False
    for line in open(f, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        ev = e.get("event")
        if ev == "start":
            ok = key in str(e.get("ckpt", ""))
            if not ok:
                return None                                 # other checkpoint: skip the rest of the file
        elif ev == "play":
            plays.append((int(e.get("tick", 0)), str(e.get("name", ""))))
        elif ev == "decision" and "rocket_tornado" in str(e.get("decision", {}).get("why", "")):
            rule += 1
    if not ok:
        return None
    rk = [t for t, n in plays if n == "Rocket"]
    tn = [t for t, n in plays if n == "Tornado"]
    combo = sum(any(abs(a - b) <= COMBO_TICKS for b in tn) for a in rk)
    return {"rocket": len(rk), "tornado": len(tn), "combo": combo, "rule": rule, "plays": len(plays)}


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "CLXIII"
    M = [m for m in (match(f, key) for f in sorted(glob.glob(str(LOGS / "live_play_*.jsonl")))) if m and m["plays"] > 0]
    n = len(M)
    if not n:
        print(f"no live matches with ckpt ~ {key}")
        return
    s = {k: sum(m[k] for m in M) for k in ("rocket", "tornado", "combo", "rule", "plays")}
    print(f"{key}: {n} matches | Rockets {s['rocket']} ({s['rocket'] / n:.2f} / match) | Tornados {s['tornado']} "
          f"({s['tornado'] / n:.2f}) | combos {s['combo']} | rule-combo decisions {s['rule']} | matches with a Rocket "
          f"{sum(m['rocket'] > 0 for m in M)}")


if __name__ == "__main__":
    main()
