"""Print the SIM card table's hero Ice Wizard ABILITY block only."""
import json, sys
p = sys.argv[1] if len(sys.argv) > 1 else 'research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json'
d = json.load(open(p, encoding='utf-8'))
for f in d['hero_forms']:
    if f.get('form_of') == 'IceWizard':
        print(json.dumps(f['ability'], indent=1)[:5000])
