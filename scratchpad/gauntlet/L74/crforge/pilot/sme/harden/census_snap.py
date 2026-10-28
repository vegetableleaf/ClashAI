"""SME-HARDEN: for the torn_step frames whose rows need the dying branch (cs.jsonl), is each such row (side, x, y) the
point of a body of that name in one of crforge's in-step states of step t+1 (SnapRun2)? python3 census_snap.py cs.jsonl"""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_DIR', '/workspace/pilot/sme10'))
import sme_live as L
import bp_snap

rows = [r for r in map(json.loads, open(sys.argv[1])) if r['dying']]
for r in rows:
    m, t = r['match'], r['t']
    plan = json.load(open('/workspace/pilot/sme_live/a10G1/%s/plan.json' % m))
    snaps = bp_snap.snapshots(L.runnable(plan), [t + 1], t + 4, '/dev/shm/sn/sn_%s_%d' % (m, t)).get(t + 1, [])
    out = []
    for d in r['dying']:
        s, x, y, hp = d['row']
        hits = [(k, e[0], e[6]) for k, st in enumerate(snaps) for e in st['E']
                if e[1] in 'TC' and (e[3], e[4], e[5]) == (s, x, y)]
        out.append([d['name'], d['row'], hits[:3], len(hits)])
    print(m, t, 'states', len(snaps), json.dumps(out))
