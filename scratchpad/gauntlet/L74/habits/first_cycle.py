"""L74/habits: at the FIRST bridge X-Bow of a match -- has the opponent shown a heavy card yet, and is it out of hand? (live, pros)"""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hablib as H, live_tables as LT, pro_tables as PT, extra as X
live, pros = LT.load(), PT.load()
for g in ['CXXIV', 'CXXXVIII', 'CLIII', 'pro icebow crawl2', 'pro icebow8 HF', 'pro other X-Bow HF']:
    M = [m for m in live + pros if m['group'] == g]
    rows = []
    for m in M:
        x = H.xbow_events(m)
        if x:
            r = x[0]; r['out'] = X.heavy_out(m, r['tick']); r['n_opp'] = sum(p['tick'] < r['tick'] for p in m['opp']); rows.append(r)
    c = Counter(r['out'] for r in rows)
    print(f"{g:20s} first bridge X-Bows {len(rows)}: opp plays seen before it (median) {sorted(r['n_opp'] for r in rows)[len(rows)//2]}; "
          f"no heavy shown {LT.pct(c[None]/len(rows))} (heavy-next {LT.pct(H.mean([r['heavy'] for r in rows if r['out'] is None]))}), "
          f"heavy possibly in hand {LT.pct(c[False]/len(rows))} (heavy-next {LT.pct(H.mean([r['heavy'] for r in rows if r['out'] is False]))}), "
          f"every heavy out of hand {LT.pct(c[True]/len(rows))} (heavy-next {LT.pct(H.mean([r['heavy'] for r in rows if r['out'] is True]))})")
