"""L74 combo (10-17): re-fit the Rocket flight and the pull-landing window from the fast-plays timing sweep (scenarios.py sweep, engine
only, oracle aim; pod1017_fastplays/fastplays/sweep.jsonl) -- every row carries the Rocket's measured deploy / impact ticks and the
Tornado's deploy, so the landing offset L = impact - Tornado deploy is MEASURED per row, not modelled.
    python fit_window.py SWEEP.jsonl
Prints (1) flight = impact - deploy vs d / 0.35 (d = aim distance from my king tower (9, 28.65)): the constant c in round(d/.35) + c;
(2) per scenario the group damage vs L, the lone Rocket's damage, and the L range where the combo holds >= 80 % of its best and
>= 1.5 x the lone Rocket (the analyze_scen window rule, here in L instead of the deploy gap)."""
import collections
import json
import math
import statistics
import sys

rows = [json.loads(s) for s in open(sys.argv[1], encoding='utf-8') if s.strip()]
res = []
for r in rows:
    if r.get('impact_tick') and r.get('rocket'):
        d = math.hypot(r['cell_xy'][0] - 9.0, r['cell_xy'][1] - 28.65)
        res.append((r['scenario'], d, r['impact_tick'] - r['rocket'][0], r['flight_rule']))
print('flight: measured - round(d/.35) per scenario (mean, min, max); rule - measured')
by = collections.defaultdict(list)
for s, d, f, fr in res:
    by[s].append((f - round(d / .35), fr - f))
allc = [c for v in by.values() for c, _ in v]
for s, v in by.items():
    c = [x for x, _ in v]
    print(f'  {s:18s} n {len(v):4d}  c {statistics.mean(c):5.2f} [{min(c)}, {max(c)}]   rule - measured {statistics.mean(x for _, x in v):+.2f}')
print(f'  ALL c mean {statistics.mean(allc):.2f} median {statistics.median(allc)}')
print('\nwindow in L = impact - Tornado deploy (damage = group hp lost at the impact, mean over sides / times)')
for s in by:
    xs = [r for r in rows if r['scenario'] == s and r.get('impact_tick')]
    lone = statistics.mean(r.get('group_hp_drop_at_impact', 0) for r in xs if r['gap'] is None)
    curve = collections.defaultdict(list)
    for r in xs:
        if r['gap'] is not None and r.get('impact_minus_tornado_deploy') is not None:
            curve[r['impact_minus_tornado_deploy']].append(r.get('group_hp_drop_at_impact', 0))
    c = {k: statistics.mean(v) for k, v in sorted(curve.items())}
    best = max(c.values())
    ok = [k for k, v in c.items() if k >= 0 and v >= 0.8 * best and v >= 1.5 * lone]
    print(f'  {s:18s} lone {lone:5.0f} best {best:5.0f}  L window {(min(ok), max(ok)) if ok else None}  tested L {min(c)}..{max(c)}')
    print('     ' + ' '.join(f'{k}:{v:.0f}' for k, v in c.items() if -2 <= k <= 50))
