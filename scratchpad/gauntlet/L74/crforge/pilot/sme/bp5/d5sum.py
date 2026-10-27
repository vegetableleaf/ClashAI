"""d5sum.py death5.jsonl -- delay-6 direct kills: kill attribution against out"""
import json, collections, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
d = [x for x in rows if x['pre'] and x['clean'] and x['delay'] == 6 and x['cause'] == 'direct']
print('delay-6 direct, clean+pre:', len(d), collections.Counter(x['out'] for x in d))
F = {'kind': lambda x: x['kind'], 'killer_is_u': lambda x: x['killer_is_u'],
     'k_before_u (step order)': lambda x: None if x['k_idx'] is None or x['u_idx'] is None else x['k_idx'] < x['u_idx'],
     'k_h<u_h (holder)': lambda x: None if x['k_h'] is None else x['k_h'] < x['u_h'],
     'r_h<u_h': lambda x: x['r_h'] < x['u_h'],
     'killer side == u side': lambda x: None,
     'hit after u': lambda x: None if x['hit_idx'] is None or x['u_idx'] is None else x['hit_idx'] > x['u_idx'],
     'u_state': lambda x: x['state'], 'u load>0': lambda x: x['timers'].split('/')[1] != '0'}
for nm, f in F.items():
    c = collections.Counter((f(x), x['out']) for x in d)
    print('%-24s' % nm, sorted(c.items(), key=str))
c = collections.Counter((x['killer_name'], x['out']) for x in d)
print(sorted(c.items(), key=lambda z: -z[1])[:25])
for x in d:
    if x['out'] != 'crforge':
        print({k: x.get(k) for k in ('m', 't', 'name', 'R', 'killer_name', 'kind', 'killer_is_u', 'u_idx', 'k_idx', 'hit_idx', 'u_h', 'r_h', 'k_h', 'timers', 'dist')})
