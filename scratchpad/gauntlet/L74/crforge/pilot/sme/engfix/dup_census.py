# dup_census.py -- ENG-FIX3: frames whose tick label repeats with different content, on the scored records' logs
import json, glob, sys
R = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/'
tot = dif = 0; rows = []
for f in sorted(glob.glob(R + 'L74/crforge/pilot/sme/engfix/r6/*_on.jsonl')):
    for l in open(f):
        m = json.loads(l)['match']
        prev = {}
        for line in open(R + 'L68/live_reader/' + m + '.jsonl', 'rb'):
            if b'"frame"' not in line[:40]:
                continue
            d = json.loads(line); t = d['tick']
            if t is None or t < 0:
                continue
            key = (sorted(tuple(e[:5]) for e in d['ents']), round(d.get('elixir') or 0, 4))
            if t in prev:
                tot += 1
                if prev[t] != key:
                    dif += 1; rows.append((m[-15:], t))
            else:
                prev[t] = key
print('dup samples', tot, 'differing', dif)
print(rows[:80])
