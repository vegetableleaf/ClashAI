"""Pilot drive progress from the four summary.jsonl files (run on the VM from ~/cb, or on a fetched copy).

    python3 progress.py [<corpus_gen_pilot dir>]    (default scratchpad/gauntlet/ext/corpus_gen_pilot)
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

O = Path(sys.argv[1] if len(sys.argv) > 1 else "scratchpad/gauntlet/ext/corpus_gen_pilot")
total = sum(len(json.loads(p.read_text())) for p in O.glob("crawl/chunk_*/tags.json"))
per, fails, done = {}, Counter(), 0
for s in range(4):
    f = O / f"s{s}" / "summary.jsonl"
    rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
    ok = [r for r in rows if r["ok"]]
    fails.update(r["error"][:70] for r in rows if not r["ok"])
    wall = sum(r["seconds"] for r in rows)
    per[f"s{s}"] = {"ok": len(ok), "failed": len(rows) - len(ok), "s_per_replay_all": round(wall / max(len(rows), 1), 2),
                    "s_per_ok_median": sorted(r["seconds"] for r in ok)[len(ok) // 2] if ok else None,
                    "crowns_match": sum(bool(r["crowns_match"]) for r in ok)}
    done += len(rows)
# wall clock since the first chunk started (row "seconds" exclude the --determinism-every re-runs, so do not sum them)
start = datetime.fromisoformat((O / "s0.log").read_text().split("=== ", 1)[1].split()[0].replace("Z", "+00:00"))
wall_h = (datetime.now(timezone.utc) - start).total_seconds() / 3600
rate = done / max(wall_h * 3600, 1e-9)                   # replays/s, all 4 slots
left_h = (total - done) / rate / 3600 if rate else None
print(json.dumps({"now_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"), "total": total, "done": done,
                  "per_slot": per, "failures": dict(fails.most_common(10)),
                  "wall_h": round(wall_h, 3), "replays_per_hour": round(rate * 3600), "hours_left": round(left_h, 2) if left_h else None,
                  "all_done": (O / "DONE").exists()}, indent=1))
