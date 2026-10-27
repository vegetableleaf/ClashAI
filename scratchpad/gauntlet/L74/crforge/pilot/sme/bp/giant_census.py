"""Hero Giant: ability casts in an inputs file vs GiantHero_Slap_Stun starts on victims (laptop)."""
import json, sys
sys.path.insert(0, '.')
import bp_rules
for l in open(sys.argv[1]):
    rec = json.loads(l)
    hero = [i for i in (0, 1) if any(rec['sides'][str(i)]['deck'][k] == 'Giant' and rec['sides'][str(i)]['slot_flags'][k] == 2 for k in range(8))]
    st = bp_rules.buff_starts(sys.argv[2] + '/' + rec['match'] + '.jsonl', 'GiantHero_Slap_Stun')
    casts = [(p['side'], p['tick'], p.get('source')) for p in rec['plays'] if p['kind'] == 'ability' and p['card'] == 'Giant']
    if st or casts:
        print(rec['match'], 'hero side', hero, 'casts', casts, 'stun c-9 (caster side)', [(1 - s, c - 9) for s, c in st])
