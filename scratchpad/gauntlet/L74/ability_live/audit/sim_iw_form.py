"""Print the SIM card table's hero Ice Wizard form (ability effect, radius) -- where the B6 head's radius comes from."""
import json, sys
p = sys.argv[1] if len(sys.argv) > 1 else 'research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json'
d = json.load(open(p, encoding='utf-8'))
for f in d['hero_forms']:
    if 'Ice' in str(f.get('form_of')):
        print(json.dumps({k: v for k, v in f.items() if k != 'tables'}, indent=1)[:4000])
