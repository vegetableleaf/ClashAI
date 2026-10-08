"""W3 SIM: Log-hits-barrel from sim_lane.py play logs (learner plays; enemy Goblin Barrels in flight at decision time).
    python sim_log_hits.py LANE_DIR [LANE_DIR ...]
Per Log played while >= 1 enemy barrel with a visible target is in flight: covers (q4.py log_hits: |dx| <= 2.5,
-1 <= log_y - landing_y <= 10.1, board-frame tiles) any barrel's landing; lane = same half as the (first) barrel."""
import json, sys
from pathlib import Path


def wilson(k, n, z=1.96):
    if not n: return "n/a"
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** .5 / d
    return f"{k}/{n} = {p:.3f} [{c - h:.3f}, {c + h:.3f}]"


for d in sys.argv[1:]:
    n = hit = lane = logs = 0
    for fn in Path(d).glob("lane_*.jsonl"):
        for line in open(fn):
            e = json.loads(line)
            if e["card"] != "the-log":
                continue
            logs += 1
            b = [p for p in e.get("barrels", []) if p[2] >= 0]
            if not b:
                continue
            X, Y = e["cell"] % 36 / 2, e["cell"] // 36 / 2          # lattice, board frame (me at the bottom)
            n += 1
            hit += any(abs(X - p[2] * 18) <= 2.5 and -1 <= Y - p[3] * 32 <= 10.1 for p in b)
            lane += (X < 9) == (b[0][2] * 18 < 9)
    print(f"{d}: Logs {logs}, with a barrel in flight {n}; covers landing (q4) {wilson(hit, n)}; lane {wilson(lane, n)}")
