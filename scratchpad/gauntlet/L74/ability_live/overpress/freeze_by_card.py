"""Freeze ticks per frozen body by card: live (live_freeze.json) vs the SIM probe (sim_probe.json, if present here)."""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

H = Path(__file__).parent
live = defaultdict(list)
for r in json.loads((H / 'live_freeze.json').read_text()):
    for z in r['frozen']:
        live[z['name'].split('_EV')[0]].append(z['ticks'])
sim = defaultdict(list)
if (H / 'sim_probe.json').is_file():
    for r in json.loads((H / 'sim_probe.json').read_text()):
        for z in r.get('frozen', []):
            sim[str(z['name'])].append(z['ticks'])
print(f"{'card':16s} {'live n':>6s} {'live med':>8s} {'live p25-p75':>14s} {'sim n':>6s} {'sim med':>7s}")
for c in sorted(set(live) | set(sim), key=lambda c: -len(live.get(c, []))):
    lv, sv = live.get(c, []), sim.get(c, [])
    if len(lv) < 8 and not sv:
        continue
    q = st.quantiles(lv, n=4) if len(lv) > 3 else [0, 0, 0]
    print(f"{c:16s} {len(lv):6d} {st.median(lv) if lv else '-':>8} {f'{q[0]:.0f}-{q[2]:.0f}':>14s} {len(sv):6d} {st.median(sv) if sv else '-':>7}")
