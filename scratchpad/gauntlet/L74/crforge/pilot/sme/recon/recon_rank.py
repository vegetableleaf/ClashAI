"""recon_rank.py RESULTS.jsonl... -- for each structural / hand-rule edit kept in the final plan (anything but a plain shift),
the search round(s) at that divergence: legal hypotheses run, how many beat d, the round's rank-1 edit and its objective."""
import json, sys

for path in sys.argv[1:]:
    for line in open(path):
        r = json.loads(line)
        if 'error' in r:
            continue
        keys = [e for e in r['edits'] if not e.startswith('shift')]
        for x in r['log']:
            if 'round' not in x or not x['best']:
                continue
            obj, best = x['best']
            if best in keys or any(best.split(' ')[0] == k.split(' ')[0] and best != k for k in keys if not best.startswith('shift')):
                print(r['match'][-6:], 'round', x['round'], 'd', x['d'], 'legal', x['legal'], 'better', x['better'],
                      'refused', x['refused'], '| rank1:', best, 'obj', obj, '| kept' if best in keys else '| NOT kept')
        for k in keys:
            if not any(x.get('best') and x['best'][1] == k for x in r['log'] if 'round' in x):
                print(r['match'][-6:], 'kept edit never rank 1 in its round:', k)
