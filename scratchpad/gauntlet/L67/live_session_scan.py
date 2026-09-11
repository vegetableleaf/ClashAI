"""L67p: per-match freeze scan of a live play.py STDOUT log (the one with [student] lines), UTF-8.

The owner's long icebow session is the freeze root-cause run (5cs.99 G/K). play.py prints timestamps only on
[play]/[nav] lines; [student] WAIT lines are rate-limited to one per 10 WAIT decisions and carry p, elixir and
(when p < 0.05) a digest with the match clock t=. So a match is segmented by `state: IN_MATCH` ... next `state:`
line, and inside it:

  plays          [student] PLAY + STALL-PLAY lines (each is one real tap)
  stall_plays    STALL-PLAY lines (the anti-stall rule fired: elixir >= 9 for 12 s with no play)
  wait_lines     [student] WAIT lines (x10 = WAIT decisions)
  pinned_lines   WAIT lines with p < 0.05
  hi_pinned      WAIT lines with p < 0.05 AND elixir >= 8   <- the freeze signature from 5cs.99 G
  longest_hi_run longest run of consecutive WAIT lines at elixir >= 8 with no play between them
  overtime       match wall duration > 200 s (regulation 180 s + end animation)

usage: python live_session_scan.py <utf8 stdout log> --out <json> [--until HH:MM:SS]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TS = re.compile(r"^(\d\d):(\d\d):(\d\d) \[")
P = re.compile(r"\bp=([0-9.]+)")
ELX = re.compile(r"\belixir (\d+)")
TCLK = re.compile(r"\bt=(\d+)s")


def secs(m, day_roll):
    s = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return s + day_roll


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    matches, cur = [], None
    last_s, roll = None, 0
    run = 0
    for line in a.log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(line)
        if m:
            s = secs(m, roll)
            if last_s is not None and s < last_s - 6 * 3600:        # crossed midnight
                roll += 86400
                s += 86400
            last_s = s
            if "[play] state: " in line:
                if cur is not None:
                    cur["end_s"] = s
                    cur["end_state"] = line.split("state: ", 1)[1].strip()
                    matches.append(cur)
                    cur = None
                if line.rstrip().endswith("state: IN_MATCH"):
                    cur = {"start": line[:8], "start_s": s, "plays": 0, "stall_plays": 0, "wait_lines": 0,
                           "pinned_lines": 0, "hi_pinned": 0, "longest_hi_run": 0, "grace_holds": 0,
                           "max_t_digest": None, "hi_pinned_t": []}
                    run = 0
            elif cur is not None and "grace hold (label lost" in line:
                cur["grace_holds"] += 1
            continue
        if cur is None or not line.startswith("[student]"):
            continue
        if line.startswith("[student] PLAY") or line.startswith("[student] STALL-PLAY"):
            cur["plays"] += 1
            cur["stall_plays"] += line.startswith("[student] STALL-PLAY")
            run = 0
        elif line.startswith("[student] WAIT"):
            cur["wait_lines"] += 1
            pm, em, tm = P.search(line), ELX.search(line), TCLK.search(line)
            p = float(pm.group(1)) if pm else None
            e = int(em.group(1)) if em else None
            if tm:
                cur["max_t_digest"] = max(cur["max_t_digest"] or 0, int(tm.group(1)))
            if p is not None and p < 0.05:
                cur["pinned_lines"] += 1
                if e is not None and e >= 8:
                    cur["hi_pinned"] += 1
                    if tm:
                        cur["hi_pinned_t"].append(int(tm.group(1)))
            if e is not None and e >= 8:
                run += 1
                cur["longest_hi_run"] = max(cur["longest_hi_run"], run)
            else:
                run = 0
    for mt in matches:
        mt["dur_s"] = mt["end_s"] - mt["start_s"]
        mt["overtime"] = mt["dur_s"] > 200
        mt["plays_per_min"] = round(mt["plays"] / max(1e-9, mt["dur_s"] / 60.0), 2)
    real = [mt for mt in matches if mt["dur_s"] >= 60]
    tot = lambda k: sum(mt[k] for mt in real)
    ot, reg = [mt for mt in real if mt["overtime"]], [mt for mt in real if not mt["overtime"]]
    summ = {
        "segments": len(matches), "matches_ge_60s": len(real), "overtime_matches": len(ot),
        "minutes_in_match": round(tot("dur_s") / 60.0, 1), "plays": tot("plays"), "stall_plays": tot("stall_plays"),
        "plays_per_min": round(tot("plays") / max(1e-9, tot("dur_s") / 60.0), 2),
        "wait_lines": tot("wait_lines"), "pinned_lines": tot("pinned_lines"), "hi_pinned": tot("hi_pinned"),
        "matches_with_hi_run_ge_5": sum(mt["longest_hi_run"] >= 5 for mt in real),
        "matches_with_hi_run_ge_10": sum(mt["longest_hi_run"] >= 10 for mt in real),
        "hi_pinned_per_min_regulation": round(sum(m["hi_pinned"] for m in reg) / max(1e-9, sum(m["dur_s"] for m in reg) / 60), 3),
        "hi_pinned_per_min_overtime": round(sum(m["hi_pinned"] for m in ot) / max(1e-9, sum(m["dur_s"] for m in ot) / 60), 3) if ot else None,
        "stall_per_min_regulation": round(sum(m["stall_plays"] for m in reg) / max(1e-9, sum(m["dur_s"] for m in reg) / 60), 3),
        "stall_per_min_overtime": round(sum(m["stall_plays"] for m in ot) / max(1e-9, sum(m["dur_s"] for m in ot) / 60), 3) if ot else None,
        "first_match": real[0]["start"] if real else None, "last_match": real[-1]["start"] if real else None,
    }
    a.out.write_text(json.dumps({"summary": summ, "matches": matches}, indent=1), encoding="utf-8")
    print(json.dumps(summ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
