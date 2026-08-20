"""Side-by-side progress for the drill-mix A/B: `--drill-frac 0.3` against a plain run.

The two arms write separate logs and separate checkpoints, and the only number that compares them
fairly is the EVAL winrate -- eval always plays pure full matches from its own pool, so it means
the same thing in both arms even though one of them trains on 10-second drills a third of the
time. The rolling `avg-N` is the one to read: a single 150-match eval carries roughly +-4pp, so
two points differing by less than that are the same point.

The drill arm also reports a DRILL PASS RATE, which is the more direct progress signal of the two:
it says whether the rehearsed interactions are actually being learned, and it moves long before a
ladder winrate does.

    python tools/ab_progress.py              # one shot
    python tools/ab_progress.py --watch      # refresh every 30s until both finish
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

ARMS = [("DRILL  (--drill-frac 0.3)", "ppo_drill.log"),
        ("CONTROL(--drill-frac 0)", "ppo_control.log")]

# [train-sim-ppo] 250 episodes: winrate=  22% avg_rew=-6.6 0.4 ep/s total 8W-28L-0D ... | drills 14 (7% pass)
RE_PROG = re.compile(r"\[train-sim-ppo\]\s+(\d+)\s+episodes:\s+winrate=\s*(-?\d+)%"
                     r".*?([\d.]+)\s+ep/s\s+total\s+(\d+)W-(\d+)L-(\d+)D")
RE_DRILL = re.compile(r"\|\s*drills\s+(\d+)\s+\((\d+)%\s+pass\)")
# [train-sim-ppo] EVAL @ 500: ladder(x) 34% (avg-3 31%) ... | 150 matches each
RE_EVAL = re.compile(r"\[train-sim-ppo\]\s+EVAL\s+@\s+(\d+):.*?\)\s+(-?\d+)%\s+\(avg-(\d+)\s+(-?\d+)%\)")
RE_DONE = re.compile(r"stopped after (\d+) match")


def read(path):
    try:
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def parse(text):
    if text is None:
        return None
    out = {"episodes": 0, "wr": None, "eps": 0.0, "w": 0, "l": 0, "d": 0,
           "drills": None, "drill_pass": None, "evals": [], "finished": None}
    for m in RE_PROG.finditer(text):
        out["episodes"] = int(m.group(1)); out["wr"] = int(m.group(2))
        out["eps"] = float(m.group(3))
        out["w"], out["l"], out["d"] = int(m.group(4)), int(m.group(5)), int(m.group(6))
    for m in RE_DRILL.finditer(text):
        out["drills"], out["drill_pass"] = int(m.group(1)), int(m.group(2))
    for m in RE_EVAL.finditer(text):
        out["evals"].append((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    m = RE_DONE.search(text)
    if m:
        out["finished"] = int(m.group(1))
    return out


def bar(pct, width=22):
    pct = max(0.0, min(1.0, float(pct)))
    n = int(round(pct * width))
    return "[" + "#" * n + "-" * (width - n) + "]"


def show(total, quiet=False):
    rows = []
    for label, fname in ARMS:
        rows.append((label, parse(read(os.path.join(DATA, fname)))))
    print("=" * 86)
    print("ICEBOW drill-mix A/B  --  %s" % time.strftime("%H:%M:%S"))
    print("=" * 86)
    for label, r in rows:
        if r is None:
            print("%-26s  log not found yet" % label)
            continue
        done = r["finished"] or r["episodes"]
        frac = done / float(total) if total else 0.0
        eta = ""
        if r["eps"] > 0 and not r["finished"] and total:
            secs = max(0, total - done) / r["eps"]
            eta = "  eta %dh%02dm" % (int(secs // 3600), int((secs % 3600) // 60))
        state = "DONE" if r["finished"] else "running"
        print("%-26s %s %5d/%d  %.2f ep/s  %s%s"
              % (label, bar(frac), done, total, r["eps"], state, eta))
        rec = "  record %dW-%dL-%dD (rollout winrate %s%%)" % (
            r["w"], r["l"], r["d"], r["wr"] if r["wr"] is not None else "?")
        if r["drills"] is not None:
            # The headline for this arm: are the rehearsed interactions actually being learned?
            rec += "   |  DRILLS %d, %d%% pass" % (r["drills"], r["drill_pass"])
        print(rec)
        if r["evals"]:
            last = r["evals"][-1]
            print("  EVAL @%d: %d%%  (rolling avg-%d %d%%)   [%d evals so far]"
                  % (last[0], last[1], last[2], last[3], len(r["evals"])))
        else:
            print("  EVAL: none yet")
        print()
    # the comparison, which is the only reason both are running
    a, b = rows[0][1], rows[1][1]
    if a and b and a["evals"] and b["evals"]:
        print("-" * 86)
        print("%-10s %-22s %-22s %s" % ("episode", "DRILL eval (avg)", "CONTROL eval (avg)", "gap"))
        ea = {e[0]: e for e in a["evals"]}
        eb = {e[0]: e for e in b["evals"]}
        for k in sorted(set(ea) | set(eb)):
            xa, xb = ea.get(k), eb.get(k)
            sa = "%3d%% (avg %3d%%)" % (xa[1], xa[3]) if xa else "-"
            sb = "%3d%% (avg %3d%%)" % (xb[1], xb[3]) if xb else "-"
            gap = ("%+d pp" % (xa[3] - xb[3])) if (xa and xb) else ""
            print("%-10d %-22s %-22s %s" % (k, sa, sb, gap))
        print()
        print("A single 150-match eval carries about +-4pp, so read the ROLLING AVERAGE and treat")
        print("gaps under ~5pp as noise. Eval is pure full matches in both arms, which is what")
        print("makes them comparable at all.")
    return all(r and r["finished"] for _, r in rows)


def main():
    ap = argparse.ArgumentParser(description="side-by-side progress for the drill-mix A/B")
    ap.add_argument("--watch", action="store_true", help="refresh until both arms finish")
    ap.add_argument("--every", type=float, default=30.0, help="seconds between refreshes")
    ap.add_argument("--total", type=int, default=4000, help="episodes each arm was asked for")
    a = ap.parse_args()
    if not a.watch:
        show(a.total)
        return
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        if show(a.total):
            print("both arms finished.")
            return
        try:
            time.sleep(a.every)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    sys.exit(main())
