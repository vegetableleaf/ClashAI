"""Live CLXIII (calibration block): attempted (play events) vs confirmed events per minute, from live_table's cache."""
import sys, statistics as st, json
from pathlib import Path
H = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/humanlike')
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent))
import card
import live_table as LT
recs = card.live_records('calibration')
ids = [r['id'] for r in recs]
A = C = 0; ap = []; cp = []; gaps_a = []; gaps_c = []
for i in ids:
    d = LT.cached(card.LOGS / i)
    if not d: continue
    mins = max(d['end'] - d['t0'], 1) / 1200.0
    conf = sorted(t for t, n in d['own_conf'] if t)
    A += len(d['mine']); C += len(conf)
    ap.append(len(d['mine']) / mins); cp.append(len(conf) / mins)
    m = sorted(d['mine']); gaps_a += [(b - a) / 20 for a, b in zip(m, m[1:])]
    gaps_c += [(b - a) / 20 for a, b in zip(conf, conf[1:])]
print('n', len(ap), 'attempted/min', round(st.mean(ap), 2), 'confirmed/min', round(st.mean(cp), 2), 'pooled attempted', A, 'confirmed', C, 'ratio', round(C / A, 3))
print('median gap attempted', round(st.median(gaps_a), 2), 'confirmed', round(st.median(gaps_c), 2))
