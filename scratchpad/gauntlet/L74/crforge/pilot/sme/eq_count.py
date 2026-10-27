"""Earthquake: two area effects at one point (Earthquake 3000 ms + EarthquakeHiddenDamage 3050 ms, both card
28000014 in the reader). Per tick offset from the sim Earthquake's last line: how many EQ effects does the sim hold at
the point, and how many does the recorded frame show?   python3 eq_count.py RUNDIR"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
tab = collections.defaultdict(collections.Counter)
for l in open(os.path.join(run, 'results.jsonl')):
    m = json.loads(l)['match']
    p = os.path.join(run, m, 'plan.json')
    if not os.path.exists(p):
        continue
    plan = json.load(open(p))
    if not any(c.get('card') == 'Earthquake' for c in plan['cmds']):
        continue
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'eq'))[0]
    if o is None:
        continue
    by = {x['t']: x for x in o}
    last = {}
    for x in o:
        for e in x['E']:
            if e[1] == 'A' and e[2] == 'Earthquake':
                last[e[0]] = (x['t'], e[3], e[4], e[5])
    for z, side, px, py in last.values():
        for d in range(-3, 5):
            t = z + d
            if t not in frames or t not in by:
                continue
            ns = sum(1 for e in by[t]['E'] if e[1] == 'A' and 'Earthquake' in e[2] and e[3] == side and e[4] == px and e[5] == py)
            nr = sum(1 for a in frames[t]['A'] if a[3] == 28000014 and a[0] == side and a[1] == px and a[2] == py)
            tab[d][(ns, nr)] += 1
print('offset from the sim Earthquake last line: {(sim count, recorded count): frames}')
for d in sorted(tab):
    print(d, dict(tab[d]))
