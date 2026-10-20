"""Rank the sunk-cost clusters: where OUR bridge X-Bows (live) are worth least AND we place them far more often than pros in
the same decision context. Excess failed bridge X-Bows per 100 of our matches = (our - pro placements per opportunity-minute)
x our opportunity-minutes per match x 100 x (1 - our lock rate there); x 6 = elixir.  python sunk.py -> sunk.out"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = {tuple(k.split('|')): v for k, v in json.load(open(HERE / 'clusters.json')).items()}
NM = 787                                    # our live matches (CXXXVIII 262, CLX 253, CLIII 168, CLIX 104)
rows = []
for (a, ctx, g), v in CL.items():
    if g != 'ours' or (a, ctx, 'pro') not in CL or v['n'] < 30:
        continue
    p = CL[(a, ctx, 'pro')]
    exc = (v['bridge_rate'] - p['bridge_rate']) * v['opp_min'] / NM * 100
    rows.append((exc * (1 - v['lock']), a, ctx, v, p, exc))
rows.sort(key=lambda t: -t[0])
out = ['cluster | ours bridge/opp-min [CI] vs pro [CI] | ratio | our lock | our next20 net | excess bridge X-Bows /100 matches | '
       'excess FAILED /100 matches (x6 = elixir)']
for f, a, ctx, v, p, exc in rows:
    out.append(f"{a}/{ctx:10s} | {v['bridge_rate']:.2f} [{v['ci'][0]:.2f}, {v['ci'][1]:.2f}] vs {p['bridge_rate']:.2f} "
               f"[{p['ci'][0]:.2f}, {p['ci'][1]:.2f}] | x{v['bridge_rate'] / p['bridge_rate']:.2f} | {v['lock']:.3f} | {v['net']:+.3f} | "
               f"{exc:5.1f} | {f:5.1f} ({6 * f:.0f} elixir)")
open(HERE / 'sunk.out', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
