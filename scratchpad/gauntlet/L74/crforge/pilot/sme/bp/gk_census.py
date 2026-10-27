"""Golden Knight: gk_dash casts in an inputs file vs GoldenKnightCharge buff instances (laptop). python -I gk_census.py INPUTS LIVE"""
import json, sys
sys.path.insert(0, '.')
import bp_rules
for l in open(sys.argv[1]):
    rec = json.loads(l)
    gk = [p for p in rec['plays'] if p['card'] == 'GoldenKnight']
    if not gk:
        continue
    st = bp_rules.buff_starts(sys.argv[2] + '/' + rec['match'] + '.jsonl', 'GoldenKnightCharge')
    print(rec['match'], 'plays', [(p['side'], p['tick']) for p in gk if p['kind'] == 'play'])
    print('   casts', [(p['side'], p['tick'], p['run_ticks'], p.get('source')) for p in gk if p['kind'] == 'ability'])
    print('   buff R', [(s, c - 1) for s, c in st])
