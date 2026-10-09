"""Rocket -> Tornado combo window table at the pipelined gap (recomputes scratchpad/gauntlet/L74/rocket_value/window_table.py,
branch worktree-agent-a3bcd39979e47277b, with the achievable minimum decision-to-decision gap).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency2/window_table2.py > window_table2.txt

Constants are that worker's SIM measurements (rocket_value/measure_combo.out; decision_options.py on that branch), not mine:
  Rocket: leaves my king tower (board (9.0, 28.65)) and flies 0.35 tile/tick: flight = round(d / 0.35) + 2 ticks
  Tornado pull: the Rocket must land PULL_LANDS_FROM..PULL_LANDS_TO = 12..33 ticks after the Tornado is deployed
  the Tornado may be decided gap..: window [lo, hi] = [max(min_gap, flight - 33), flight - 12], where d ticks after the Rocket
  is also the gap between the two DEPLOYS (same action delay).
Here the only change is min_gap: 30 (their FOLLOW_MIN_GAP_TICKS = the pending lock: 28-tick confirmation + next frame) vs what a
pipelined second tap reaches. Gap numbers: stage_chain.txt (2.1 ticks median / 2.9 p95 to the second tap; frames are 2 ticks
apart) -> planning gaps 2, 3, 4 (4 = one frame later than the p95 case), then 6 / 10 for safety and 26 / 30 for today.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.decision_options import cell_centres_tiles  # noqa: E402

SPEED, KING = 0.35, (9.0, 28.65)
PULL_FROM, PULL_TO = 12, 33
GAPS = (2, 3, 4, 6, 10, 20, 26, 30, 34, 40)


def flight(cx, cy):
    return int(round(math.hypot(cx - KING[0], cy - KING[1]) / SPEED)) + 2


def plan(cx, cy, min_gap):
    f = flight(cx, cy)
    lo, hi = max(min_gap, f - PULL_TO), f - PULL_FROM
    return (lo, hi) if lo <= hi else None


print("flight (ticks) per distance from my king tower; Tornado decision window [lo, hi] ticks after the Rocket decision")
head = " | ".join(f"gap>={g}" for g in (2, 4, 10, 26, 30))
print(f"  d tiles  flight | {head}")
for d in (3, 5, 7, 9, 11, 13, 14, 15, 17, 20, 23):
    f = int(round(d / SPEED)) + 2
    cells = []
    for g in (2, 4, 10, 26, 30):
        lo, hi = max(g, f - PULL_TO), f - PULL_FROM
        cells.append(f"[{lo},{hi}]" if lo <= hi else "none")
    print(f"  d={d:>2}    {f:>3}   | " + " | ".join(f"{c:>9}" for c in cells))

x, y = cell_centres_tiles("lattice")
mine = y >= 16.0
print(f"\nmy-half cells: {int(mine.sum())}   (cell fraction with a feasible Tornado time at a minimum gap)")
for g in GAPS:
    ok = np.array([plan(cx, cy, g) is not None for cx, cy in zip(x[mine], y[mine])])
    ymax = y[mine][ok].max() if ok.any() else float("nan")
    wide = np.array([(plan(cx, cy, g) or (0, -99))[1] - (plan(cx, cy, g) or (0, -99))[0] >= 4 for cx, cy in zip(x[mine], y[mine])])
    tag = {2: "pipelined, median", 3: "pipelined, p95", 4: "pipelined, +1 frame", 26: "today's observed minimum",
           30: "rocket_value worker's FOLLOW_MIN_GAP (pending lock)"}.get(g, "")
    print(f"  min gap {g:>2} ticks: {int(ok.sum()):>4} cells ({ok.mean():6.1%}), deepest y {ymax:5.1f}  window >= 5 ticks wide (robust to the 2-tick frame grid): {wide.mean():6.1%}  {tag}")

# the price: both cards must be paid at once. Elixir needed AT the Rocket decision for Rocket 6 + Tornado 3, counting the regen
# before the Tornado is paid (their rule: my_elixir - 6 + regen*gap >= 3); the pipelined tap pays it after ~gap ticks, not 30
print("\nelixir needed at the Rocket decision (Rocket 6 + Tornado 3 = 9, minus the regeneration inside the gap)")
for name, per_tick in (("1x", 1 / 56), ("2x", 2 / 56), ("3x/OT", 3 / 56)):
    row = "  ".join(f"gap {g:>2}: {9 - per_tick * g:5.2f}" for g in (2, 4, 10, 30))
    print(f"  {name:>5}  {row}")
