"""WIN_TIMES json (tag -> [t_sec]) from an iteration-1 fires dir: every decision that played a rocket_value Rocket.
   python mk_times.py FIRES_DIR OUT.json [why]"""
import glob, json, sys
from collections import defaultdict
why = sys.argv[3] if len(sys.argv) > 3 else 'rocket_value'
o = defaultdict(list)
for f in glob.glob(sys.argv[1] + '/rv_*.jsonl'):
    for l in open(f):
        d = json.loads(l)
        if d['kind'] == 'rocket' and d.get('why') == why:
            o[d['tag']].append(d['t_sec'])
json.dump(o, open(sys.argv[2], 'w'))
print(len(o), 'tags', sum(map(len, o.values())), 'fires')
