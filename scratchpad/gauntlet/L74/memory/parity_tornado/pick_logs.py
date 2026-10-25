"""Pick the census matches where OUR king was damage-woken with both princesses up and our own Tornado was cast in the
80 ticks before the trigger (the Tornado-to-king situations), ext logs only. Prints one stem per line.
  python pick_logs.py CENSUS.json"""
import json, sys
d = json.load(open(sys.argv[1]))
for m in d['matches']:
    if 'king' not in m or not m.get('ext'):
        continue
    for k in m['king']:
        if (k['side'] == 'own' and k.get('cause') == 'damage' and k.get('tornado_before') is not None
                and (k['down'] is None or k['down'] > k['trigger'] + 4)):
            print(m['match'])
            break
