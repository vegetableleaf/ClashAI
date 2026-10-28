"""Group plant misses by (base class, plant kind, now class) and print an example each with the planted row and both
provenances. python3 miss_insp.py rsm.jsonl"""
import collections, json, sys
sys.path.insert(0, '/workspace/pilot/sme11')
import sme_live as L

g = collections.defaultdict(list)
for r in map(json.loads, open(sys.argv[1])):
    for x in r['plants']['missed']:
        t, cat, base, name, now, bp, np_ = x
        g[(base, name.split('_')[-1], now)].append((r['match'], t, name, bp, np_))
for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
    print(len(v), k)
    for m, t, name, bp, np_ in v[:2]:
        f = L.load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)[t]
        row = None
        if name.startswith('body'):
            row = f['E'][int(name[4:].split('_')[0])]
        print('   ', m, t, name, 'row', row, 'el', f['el'])
        print('      base', json.dumps(bp)[:400])
        print('      now ', json.dumps(np_)[:400])
