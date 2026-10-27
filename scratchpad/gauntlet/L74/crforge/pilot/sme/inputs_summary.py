"""Summary of the recovered inputs: python3 inputs_summary.py FITDIR POLDIR"""
import json, sys, collections
fl = [x for x in map(json.loads, open(sys.argv[1] + '/fit_log.jsonl')) if 'R' in x]
plan = json.load(open(sys.argv[2] + '/plan.json'))
obs = [json.loads(l) for l in open(sys.argv[2] + '/full/o0.jsonl')]
plays = [p for o in obs for p in o['plays']]
ab = [a for o in obs for a in o['ab']]
c = collections.Counter()
for x, cmd in zip(fl, plan['cmds']):
    c['kind_' + x['kind']] += 1
    c['side%d' % x['side']] += 1
    c['R-t_prev=%d' % (cmd['run'] - x['t_prev'])] += 1
    c['gap t-t_prev=%d' % (x['t'] - x['t_prev'])] += 1
    if x['kind'] == 'play':
        an = x['anchor']
        c['anchor_' + (an[2][:5] if an else 'none')] += 1
        c['point=anchor(rounded)' if an and (cmd['x'], cmd['y']) == (round(an[0]), round(an[1])) else 'point!=anchor'] += 1
print(dict(sorted(c.items())))
print('plays run', len(plays), 'placed', sum(p[2] for p in plays), 'refused(matchCode!=0)', sum(p[4] != 0 for p in plays))
print('abilities', [(a[0], a[1], a[2][:40]) for a in ab])
print('points != anchor:', [(x['card'], x['t'], x['anchor'], (cmd['x'], cmd['y'])) for x, cmd in zip(fl, plan['cmds'])
       if x['kind'] == 'play' and not (x['anchor'] and (cmd['x'], cmd['y']) == (round(x['anchor'][0]), round(x['anchor'][1])))])
