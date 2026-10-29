"""ENG-FIX5: copy an inputs record with the plays of the given (kind, card, tick) removed.
python drop_play.py IN.jsonl OUT.jsonl KIND:CARD:TICK [...]"""
import json, sys
drop = [(k, c, int(t)) for k, c, t in (a.split(':') for a in sys.argv[3:])]
with open(sys.argv[2], 'w') as w:
    for l in open(sys.argv[1]):
        r = json.loads(l)
        n = len(r['plays'])
        r['plays'] = [p for p in r['plays'] if (p['kind'], p.get('card'), p['tick']) not in drop]
        print(r['match'], 'dropped', n - len(r['plays']))
        w.write(json.dumps(r) + '\n')
