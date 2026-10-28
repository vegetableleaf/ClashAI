"""samerun9.py RUNDIR -- A2c-9R census: plays of both sides sharing a run tick in every plan (after repair) of a run: count, plan
order (which side is queued first), cards, own/opponent, and whether the match is clean at that tick (first divergence after it)."""
import collections, glob, json, os, sys
rd = sys.argv[1]
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(rd, 'results.jsonl'))}
c = collections.Counter()
for f in sorted(glob.glob(rd + '/live_play_*/plan.json')):
    m = f.split('/')[-2]
    cmds = json.load(open(f))['cmds']
    g = collections.defaultdict(list)
    for i, x in enumerate(cmds):
        if x.get('kind') == 'play': g[x['run']].append(i)
    fd = res.get(m, {}).get('first_div')
    for run, ix in sorted(g.items()):
        if len({cmds[i]['side'] for i in ix}) < 2: continue
        first = cmds[ix[0]]['side']
        clean = fd is None or fd > run
        c[(first, clean)] += 1
        print(m[10:], run, 'first_side', first, 'clean' if clean else 'after_div(%s)' % fd, 'flags' if res.get(m, {}).get('flags') else '',
              [(cmds[i]['side'], cmds[i]['card'], (cmds[i].get('_src') or {}).get('source')) for i in ix])
print('pairs by (plan-first side, clean):', dict(c))
