"""Gaps between consecutive match starts (health_rows.jsonl stems) -> picks the watcher's no-progress threshold."""
import json
from datetime import datetime
from pathlib import Path
rows = [json.loads(l) for l in open(Path(__file__).parent / "results" / "health_rows.jsonl")]
ts = sorted(datetime.strptime(r["stem"][10:25], "%Y%m%d_%H%M%S") for r in rows)
gaps = sorted(((b - a).total_seconds() / 60, a.strftime("%m-%d %H:%M")) for a, b in zip(ts, ts[1:]))
print("n", len(ts), "gaps (min): median", gaps[len(gaps) // 2][0], "p99", gaps[int(len(gaps) * .99)][0])
print("largest 12:", [(round(g, 1), t) for g, t in gaps[-12:]])
print(">10 min:", sum(g > 10 for g, _ in gaps), " >15:", sum(g > 15 for g, _ in gaps), " >20:", sum(g > 20 for g, _ in gaps))
