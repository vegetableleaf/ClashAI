"""Reader-representation evidence from the episode onsets of a run: for every sim-only object, is there a
recorded-only object of another class at the very same (side, x, y) in the same frame?
    python3 repr_stats.py RUNDIR   -> prints per sim name: n onsets, co-located recorded classes/names, none"""
import collections, json, os, sys

co, recco = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
for l in open(os.path.join(sys.argv[1], 'results.jsonl')):
    r = json.loads(l)
    for e in r.get('episodes', []):
        d = e['detail'] or []
        rec_only = {tuple(x[1][:3]): (x[0][0], x[2]) for x in d if 'rec_only' in x[0] and isinstance(x[1], list)}
        sim_only = {tuple(x[1][:3]): (x[0][0], x[2]) for x in d if 'sim_only' in x[0] and isinstance(x[1], list)}
        for pos, (cls, name) in sim_only.items():
            hit = rec_only.get(pos)
            co[name][('%s:%s' % hit) if hit else 'none'] += 1
        for pos, (cls, name) in rec_only.items():
            hit = sim_only.get(pos)
            recco[name][('%s:%s' % hit) if hit else 'none'] += 1
print('SIM-ONLY names: co-located recorded-only object (class:name) or none')
for name, c in sorted(co.items(), key=lambda kv: -sum(kv[1].values())):
    print('%5d %-36s %s' % (sum(c.values()), name, dict(c.most_common(4))))
print('REC-ONLY names: co-located sim-only object or none')
for name, c in sorted(recco.items(), key=lambda kv: -sum(kv[1].values()))[:40]:
    print('%5d %-36s %s' % (sum(c.values()), name, dict(c.most_common(4))))
