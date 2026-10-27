"""Census: every hero Valkyrie ability in an inputs file vs the reader's charge-buff starts (laptop, raw logs).
python -I valk_census.py INPUTS LIVE_DIR"""
import json, sys, collections
sys.path.insert(0, '.')
import bp_rules
inp = [json.loads(l) for l in open(sys.argv[1])]
c = collections.Counter()
for rec in inp:
    vs = [p for p in rec['plays'] if p['kind'] == 'ability' and p['card'] == 'Valkyrie']
    if not vs:
        continue
    starts = bp_rules.buff_starts(sys.argv[2] + '/' + rec['match'] + '.jsonl', bp_rules.VALK_BUFF)
    new = bp_rules.valk_from_buff(vs, starts)
    for p, q in zip(vs, new):
        d = q['tick'] - p['tick'] if q.get('dated') == 'valk_buff' else None
        c[(p.get('source'), d)] += 1
        print(rec['match'], p['side'], p.get('source'), p['tick'], p['run_ticks'], '->', q['tick'] if d is not None else '-', d)
    used = {q['tick'] + 1 for q in new if q.get('dated') == 'valk_buff'}
    for s, t in starts:
        if t not in used:
            print(rec['match'], 'UNUSED charge start', s, t)
            c['unused_start'] += 1
print(sorted(c.items(), key=str))
