"""Q1 SIM: share of idle games (< 5 accepted learner plays) per benchmark run, vs S1 (never initiates) and gen."""
import json, glob, collections, os
from common import wilson
agg = collections.defaultdict(lambda: [0, 0])
for d in sorted(glob.glob('sim/*/')):
    name = os.path.basename(os.path.normpath(d))
    rows = [json.loads(l) for l in open(os.path.join(d, 'matches.jsonl'))]
    variant = name.split('_live2')[-1] or '_base'
    for opp in ('s1', 'gen'):
        r = [x for x in rows if x['opp'] == opp]
        k = sum(x['plays_accepted'] < 5 for x in r); n = len(r)
        pl = sorted(x['plays_accepted'] for x in r)
        stalls = sum(x.get('stall_plays', 0) or 0 for x in r)
        agg[(variant, opp)][0] += k; agg[(variant, opp)][1] += n
        print('%-26s %-4s idle %2d/%d = %.2f [%.2f, %.2f]  median plays %s' % (name, opp, k, n, *wilson(k, n), pl[n // 2]))
print('\npooled over react/reactlad x sb/sc:')
for (v, o), (k, n) in sorted(agg.items()):
    print('%-8s %-4s %d/%d = %.2f [%.2f, %.2f]' % (v, o, k, n, *wilson(k, n)))
