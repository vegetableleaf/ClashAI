"""Round 7: every extracted ability cast of a hero vs the reader's ability buff and pending flag on that hero.
    icebow/.venv/Scripts/python.exe -I herobuf7.py INPUTS.jsonl HERO UNITNAME BUFFSUBSTR
Per cast (inputs' tick / source / window): the hero unit's pending_on_body rise tick, cast_timer, and each matching buff's
made tick = first sighting - (duration - remaining) / 50, nearest to the cast."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[6]
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
inp, hero, uname, sub = sys.argv[1:5]
for l in open(inp):
    r = json.loads(l)
    casts = [p for p in r['plays'] if p['kind'] == 'ability' and p['card'] == hero]
    if not casts:
        continue
    made, rise, prevp = [], [], {}
    seen = set()
    for line in open(LIVE / (r['match'] + '.jsonl'), 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line); t = d['tick']
        if t is None or t in seen:
            continue
        seen.add(t)
        for u in (d.get('phase2') or {}).get('units', []):
            if u['name'] != uname:
                continue
            for b in u.get('buffs') or []:
                if sub in b['name'] and b['duration_ms_raw']:
                    m = t - (b['duration_ms_raw'] - b['remaining_ms_raw']) // 50
                    if not any(abs(m - x[1]) <= 2 and x[0] == u['side'] for x in made):
                        made.append((u['side'], m, t, b['name']))
            ab = u.get('ability') or {}
            p = ab.get('pending_on_body')
            if p == 1 and prevp.get(u['generation']) != 1:
                rise.append((u['side'], t))
            prevp[u['generation']] = p
    for c in casts:
        mm = min((x for x in made if x[0] == c['side']), key=lambda x: abs(x[1] - c['tick']), default=None)
        rr = max((x[1] for x in rise if x[0] == c['side'] and x[1] <= c['tick'] + 5), default=None)
        print(r['match'][-15:], 'side', c['side'], 'R', c['tick'], c.get('source'), c.get('dated'), c['run_ticks'],
              'buff_made', mm and (mm[1], mm[1] - c['tick'], mm[3]), 'pending_rise', rr and (rr, rr - c['tick']))
