"""The replayed events of the fights anchored on a Goblin Drill play (a FIN match json): every GoblinDrill event in each.
  python drill_events.py MATCH_JSON [MAX]"""
import json, sys
d = json.load(open(sys.argv[1]))
k = 0
for fi in d['fights']:
    a = fi.get('anchor') or {}
    if a.get('name') != 'GoblinDrill':
        continue
    evs = [e for e in (fi.get('events') or []) if isinstance(e, dict) and e.get('name') == 'GoblinDrill']
    print('t0', fi['t0'], 'anchor', {x: a.get(x) for x in ('tick', 'x', 'y', 'source', 'form', 'side')}, 'tower live/sim',
          (fi.get('card') or {}).get('live', {}).get('tower'), ((fi.get('card') or {}).get('sim') or [{}])[0].get('tower'))
    for e in evs:
        print('    ', {x: e.get(x) for x in ('tick', 'x', 'y', 'source', 'form', 'side', 'dig', 'tap')})
    k += 1
    if k >= int(sys.argv[2] if len(sys.argv) > 2 else 4):
        break
