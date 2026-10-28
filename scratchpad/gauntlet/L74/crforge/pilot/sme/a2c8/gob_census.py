"""hero Goblins abilities (A2c round 8, 224856): per ability in the inputs, whether the reader shows the side's banner
(card 203000002 kind 13, hp > 1000) at its tick and any goblin (kind 14/15) of the side. python -I gob_census.py INPUTS"""
import json, sys
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\sme')
import live_frames
GID = 203000002
for l in open(sys.argv[1]):
    r = json.loads(l)
    ab = [p for p in r['plays'] if p['kind'] == 'ability' and p['card'] == 'Goblins']
    if not ab:
        continue
    fr = live_frames.convert(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\%s.jsonl' % r['match'])
    for p in ab:
        f = min(fr, key=lambda f: abs(f['t'] - p['tick']))
        rows = [e for e in f['E'] if e[0] == p['side'] and e[3] == GID]
        ban = [e[1:3] for e in rows if e[5] == 13]
        gob = sum(1 for e in rows if e[5] in (14, 15))
        print(r['match'], r['flags'][:1], 'side', p['side'], 'me' if p['side'] == r['my_side'] else 'opp', p['tick'], p['run_ticks'],
              p.get('source'), 'banner', ban, 'goblins', gob)
