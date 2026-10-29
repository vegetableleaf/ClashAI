# banner_census.py -- ENG-FIX3: which records can SME_BANNER_GIVEN change? A hero Goblins ability (kind ability, card Goblins)
# whose side made an earlier hero Goblins play (form 2) before the latest play preceding the press = a banner could stand before g.
import json, glob
H = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/engfix/'
for f in sorted(glob.glob(H + 'r6/*_on.jsonl')):
    for l in open(f):
        x = json.loads(l)
        ab = [p for p in x['plays'] if p['kind'] == 'ability' and p['card'] == 'Goblins']
        if not ab:
            continue
        pl = [p for p in x['plays'] if p['kind'] == 'play' and p['card'] == 'Goblins']
        rows = [(a['tick'], a['side'], [q['tick'] for q in pl if q['side'] == a['side'] and q['tick'] < a['tick']]) for a in ab]
        risk = any(len(r[2]) >= 2 for r in rows)
        print(f.split('/')[-1], x['match'][-15:], 'flags', x['flags'], 'presses', rows, 'EARLIER_PLAY' if risk else '')
