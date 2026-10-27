"""Episodes of given matches in a run. python3 eps.py RUN M1 [M2...]"""
import json, os, sys
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(sys.argv[1], 'results.jsonl'))}
for m in sys.argv[2:]:
    r = res[m]
    print(m, r.get('counts'), 'first', r.get('first_div'))
    for e in r.get('episodes', [])[:6]:
        d = [x for x in (e.get('detail') or []) if 'rec_only' in x[0] or 'sim_only' in x[0] or 'elixir' in x[0]][:3]
        print('   ', e['start'], e['end'], e['healed'], e['frames'], json.dumps(d)[:300])
