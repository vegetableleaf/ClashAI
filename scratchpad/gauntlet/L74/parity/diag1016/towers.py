"""Tower-error attribution for strict fights of chosen anchor groups, replayed with the CURRENT fights.py.
For each failing tower: first tick |live-sim| damage gap > 150, the drop amounts live/SIM in the 10 ticks before it, and
the enemy bodies within 9 tiles of that tower (live, SIM). usage: towers.py OUT.jsonl GROUP[,GROUP] [mode]"""
import json, math, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import capture, setup, F
out = open(sys.argv[1], 'w'); groups = sys.argv[2].split(','); mode = sys.argv[3] if len(sys.argv) > 3 else 'strict'
src = Path('C:/Users/benpe/pod_backup_weekend/rt35/FIGHTS35/matches')
want = defaultdict(set)
for p in sorted(src.glob('*.json')):
    d = json.loads(p.read_text())
    if d['summary'].get('skipped'): continue
    for r in d['fights']:
        if 'error' in r or not F.is_clean(r, mode): continue
        a = r['anchor']; g = ('own ' if r['own'] else 'opp ') + a['name'] + ('', ' evo', ' hero')[a['form']]
        if g in groups: want[p.stem].add(r['t0'])
for stem, t0s in sorted(want.items()):
    ctx = setup(stem)
    res, _ = capture(stem, lambda f, a: f['t0'] in t0s, ctx)
    cat = ctx['catalog']
    for f, a, rows, st, r in res:
        if not rows or 'towers' not in r: continue
        r['match'] = stem; r.update(anchor={k: a[k] for k in ('side', 'name', 'form', 'tick', 'source')}, own=a['side'] == ctx['m']['side'], obs=ctx['m']['side'])
        v = F.fight_verdict(r, 150)
        if not F.is_clean(r, mode): continue
        rec = dict(match=stem, t0=f['t0'], anchor=a['name'], agree=v['agree'], alive=v['alive_agree'], first=v['first_death_agree'], towers=[])
        for k, t in r['towers'].items():
            if abs(t['live']-t['sim']) <= max(150, .15*abs(t['live'])): continue
            L0 = next(b['hp'] for b in rows[0][1] if b['id'] == k); S0 = next(b['hp'] for b in rows[0][2] if b['id'] == k)
            ser = []
            for tick, live, simb in rows:
                lh = next((b['hp'] for b in live if b['id'] == k), 0); sh = next((b['hp'] for b in simb if b['id'] == k), 0)
                ser.append((tick, L0-max(0, lh), S0-max(0, sh)))
            first = next((s for s in ser if abs(s[1]-s[2]) > 150), ser[-1])
            i = ser.index(first)
            drops = lambda j: [(ser[q][0], ser[q][j]-ser[q-1][j]) for q in range(max(1, i-6), min(len(ser), i+3)) if ser[q][j] != ser[q-1][j]]
            tw = next(b for b in rows[i][1] if b['id'] == k)
            near = lambda bodies, key: sorted((round(math.hypot(b['x']-tw['x'], b['y']-tw['y'])/1000, 1), key(b)) for b in bodies
                                             if not b['tower'] and b['side'] != tw['side'] and math.hypot(b['x']-tw['x'], b['y']-tw['y']) < 9000)
            rec['towers'].append(dict(tower=k, own=int(k[1]) == ctx['m']['side'], live=t['live'], sim=t['sim'], first_tick=first[0]-f['t0'],
                                      live_drops=drops(1), sim_drops=drops(2),
                                      near_live=near(rows[i][1], lambda b: cat.get(b['card_id'], {}).get('display_name')),
                                      near_sim=near(rows[i][2], lambda b: b['name'])))
        out.write(json.dumps(rec)+'\n'); out.flush()
    print(stem, len(res), flush=True)
