"""Summarise sim_tornado_*.json: per unit, baseline vs each Tornado spot / trigger.   python sim_tornado_table.py <json>"""
import json
import sys

d = json.load(open(sys.argv[1]))
print('royalesim', d['royalesim'])
print('unit | mass | range | bldg-only | baseline princess lost / king active | per spot: trig -> pull tiles, target 2 s after, '
      'king active (tick after cast), princess lost')
by = {}
for r in d['runs']:
    by.setdefault(r['unit'], []).append(r)
for u, rs in by.items():
    b = next((r for r in rs if r.get('spot') is None), {})
    if b.get('error'):
        print(u, 'ERROR', b['error'])
        continue
    line = [f"{u:12s} | {b.get('mass')} | {b.get('range')} | {b.get('buildings_only')} | base P {b.get('princess_lost')} K "
            f"{'yes' if b.get('king_active_tick') else 'no'}"]
    for spot in ('pro_spot', 'king_pocket', 'mid', 'princess'):
        cells = []
        for r in rs:
            if r.get('spot') != spot:
                continue
            ka = r['king_active_tick'] - r['cast_tick'] if r.get('king_active_tick') and r.get('cast_tick') else None
            cells.append(f"{r['trig']:.0f}:{r['pull_tiles']},{r['target_after']},K{'+' + str(ka) if ka is not None else '-'},"
                         f"P{r['princess_lost']}")
        line.append(f"{spot}: " + ' '.join(cells))
    print(' || '.join(line))
