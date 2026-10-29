"""CLXIII SIM win + sum of end ticks (the outcome-identity check) per run_closed rows dir.  python -I win_b.py DIR [DIR ...]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "succ48"))
import xbow_count as XC  # noqa: E402
for d in sys.argv[1:]:
    rs = [r for r, _ in XC.rows(d)]
    w = sum(r["outcome"] == "win" for r in rs)
    print(f"{d}: games {len(rs)} CLXIII win {w} ({w / max(1, len(rs)):.2%}) sum end_tick {sum(int(r['end_tick']) for r in rs)}"
          f" outcomes {sorted(set(r['outcome'] for r in rs))}")
