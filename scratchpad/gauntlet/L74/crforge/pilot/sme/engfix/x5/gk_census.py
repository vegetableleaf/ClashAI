"""ENG-FIX5: every Golden Knight ability in the records (source gk_dash / gk_buff, dated gk_buff): the burst pair that
made the gk_dash cast (the frame at tick + 2 and the frame before), its Manhattan and Euclidean speed per tick, and the
knight's Euclidean speed over the next two frames. A walk (raged or not) stays under ~85 Euclidean; a dash runs ~250.
python -I gk_census.py LIVE_DIR INPUTS.jsonl [...]"""
import json, math, os, sys
from pathlib import Path
S = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
sys.path.insert(0, str(S))
import live_frames  # noqa: E402
GK = 26000074


def near(fr, t, side, pt):
    c = [e for e in fr[t]['E'] if e[0] == side and e[3] == GK] if t in fr else []
    return min(c, key=lambda e: abs(e[1] - pt[1]) + abs(e[2] - pt[2])) if c and pt else (c[0] if c else None)


for f in sys.argv[2:]:
    for l in open(f):
        r = json.loads(l)
        gk = [p for p in r['plays'] if p.get('card') == 'GoldenKnight' and p['kind'] == 'ability']
        if not gk:
            continue
        fr = {x['t']: x for x in live_frames.convert(os.path.join(sys.argv[1], r['match'] + '.jsonl'))}
        ts = sorted(fr)
        for p in gk:
            b = p['run_ticks'][1] + 2 if p.get('source') == 'gk_dash' and not p.get('dated') else p['tick'] + 2
            if b not in fr:
                b = min((t for t in ts if t >= b), default=None)
            if b is None:
                continue
            a = max((t for t in ts if t < b), default=None)
            eb = near(fr, b, p['side'], None)
            ea = near(fr, a, p['side'], eb) if a is not None else None
            if not (ea and eb):
                print(r['match'][10:], p['tick'], p.get('source'), p.get('dated'), 'no knight pair'); continue
            dx, dy, dt = eb[1] - ea[1], eb[2] - ea[2], b - a
            c = min((t for t in ts if t >= b + 2), default=None)
            ec = near(fr, c, p["side"], eb) if c is not None else None
            nxt = math.hypot(ec[1] - eb[1], ec[2] - eb[2]) / (c - b) if ec else -1
            print('%s %d %s %s pair %d-%d man %.0f euc %.0f next_euc %.0f' % (r['match'][10:], p['tick'], p.get('source'),
                  p.get('dated'), a, b, (abs(dx) + abs(dy)) / dt, math.hypot(dx, dy) / dt, nxt))
