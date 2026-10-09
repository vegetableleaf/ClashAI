"""Seed subsets for the arms from the scout (rv2_scout_s0.py): the seeds on which each variant's trigger held at least once on BASE's own
boards -- the only matches the arm can differ from BASE in -- plus CONTROL seeds on which it cannot (they must come out identical).
  python mk_subsets.py SCOUT_DIR OUT_DIR [--controls 12] [--arms a,b,c]
Writes OUT_DIR/<arm>_<census>.txt (comma list of seeds; empty file = no fires) and prints trigger counts per variant and census."""
import argparse, glob, json, os, random
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument('scout'); ap.add_argument('out')
ap.add_argument('--controls', type=int, default=12)
ap.add_argument('--arms', default='')
ap.add_argument('--censuses', default='evo,lad')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
random.seed(0)
censuses = a.censuses.split(',')
trig = {c: defaultdict(dict) for c in censuses}          # census -> variant -> tag -> first-trigger record
alltags = {c: set() for c in censuses}
for c in censuses:
    for f in glob.glob(f'{a.scout}/fires_base_{c}/scout_*.jsonl'):
        for line in open(f):
            r = json.loads(line)
            trig[c][r['v']][r['tag']] = r
    p = f'{a.scout}/base_{c}/matches.jsonl'
    for line in open(p):
        r = json.loads(line)
        if r.get('arm') == 'plain':
            alltags[c].add(r['tag'])
names = sorted({v for c in censuses for v in trig[c]})
want = set(a.arms.split(',')) if a.arms else set(names)
print(f'{"variant":16s} ' + ' '.join(f'{c:>14s}' for c in censuses) + '   (matches with a trigger / matches simulated so far)')
for v in names:
    row = []
    for c in censuses:
        tags = trig[c][v]
        done = alltags[c]
        seeds = sorted(int(t.split(':')[-1]) for t in tags)
        rest = sorted(int(t.split(':')[-1]) for t in done - set(tags))
        ctrl = sorted(random.sample(rest, min(a.controls, len(rest))))
        if v in want:
            open(f'{a.out}/{v}_{c}.txt', 'w').write(','.join(map(str, sorted(set(seeds) | set(ctrl)))))
        row.append(f'{len(seeds):>5d}/{len(done):<4d} {len(seeds) / max(len(done), 1):5.0%}')
    print(f'{v:16s} ' + ' '.join(f'{x:>14s}' for x in row))
