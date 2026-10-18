"""Q2 live side: every Hero IW ice cube in the phase-3 / phase-2 reader captures (icebow/data/p3_captures/*/frames.jsonl).
Per cube (= one press): life (first..last frame it is seen), hp series (does it take damage / die early?), position;
per enemy body under IceWizardHero_FreezeBuff: freeze ticks, its distance to the cube at first freeze; the after-slow
IceWizardHero_SlowBuff duration; enemies inside 2.5 tiles of the cube that never got frozen.
Output: live_freeze.json (one row per cube) + a printed summary."""
import json, glob, sys, statistics as st
from pathlib import Path
from collections import defaultdict
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/Users/benpe/ClashBot/icebow/data/p3_captures')
KEYS = (b'IceWizardHero_IceCube', b'IceWizardHero_FreezeBuff', b'IceWizardHero_SlowBuff')
rows = []
for fr in sorted(ROOT.glob('*/frames.jsonl')):
    cubes = {}                       # gen -> dict
    frozen = defaultdict(dict)       # gen -> {first,last,name,side,d0,cube}
    slow = defaultdict(list)
    near = defaultdict(set)          # cube gen -> enemy gens within 2.5 tiles at any frame while it lives
    ticks = []
    with open(fr, 'rb') as f:
        for raw in f:
            if not any(k in raw for k in KEYS):
                continue
            try: j = json.loads(raw)
            except ValueError: continue
            p = j.get('phase2') or {}
            if not p.get('valid'): continue
            t = j['game_tick']; ticks.append(t)
            ents = {e['address']: e for e in j.get('entities', [])}
            units = p.get('units', [])
            live_cubes = []
            for u in units:
                e = ents.get(u['address'])
                if u['name'] == 'IceWizardHero_IceCube' and e:
                    c = cubes.setdefault(u['generation'], dict(first=t, side=u['side'], x=e['x'], y=e['y'], hp=[], max_hp=e['max_hp']))
                    c['last'] = t; c['hp'].append(e['hp']); live_cubes.append((u['generation'], c))
            for u in units:
                e = ents.get(u['address'])
                for b in u.get('buffs') or []:
                    if b['name'] == 'IceWizardHero_FreezeBuff':
                        z = frozen[u['generation']]
                        if not z:
                            cg = min(live_cubes, key=lambda gc: (gc[1]['x']-e['x'])**2+(gc[1]['y']-e['y'])**2)[0] if live_cubes and e else None
                            z.update(first=t, name=u['name'], side=u['side'], cube=cg,
                                     d0=(((cubes[cg]['x']-e['x'])**2+(cubes[cg]['y']-e['y'])**2)**.5/1000) if cg else None,
                                     hp0=e['hp'] if e else None)
                        z['last'] = t
                        if e: z['hp1'] = e['hp']
                    elif b['name'] == 'IceWizardHero_SlowBuff':
                        slow[u['generation']].append((t, b['remaining_ms_raw'], b['duration_ms_raw']))
            for cg, c in live_cubes:
                for u in units:
                    e = ents.get(u['address'])
                    if e and u['side'] != c['side'] and e['card_id'] != -1 and e['kind'] not in (12, 13) and \
                            ((c['x']-e['x'])**2+(c['y']-e['y'])**2) <= 2500**2:
                        near[cg].add(u['generation'])
    dt = st.median([b-a for a, b in zip(ticks, ticks[1:]) if b > a]) if len(ticks) > 2 else None
    for cg, c in cubes.items():
        fz = {g: z for g, z in frozen.items() if z.get('cube') == cg}
        rows.append(dict(capture=fr.parent.name, cube=cg, frame_dt=dt, life_ticks=c['last']-c['first'], cube_hp_min=min(c['hp']),
                         cube_max_hp=c['max_hp'], cube_hp_last=c['hp'][-1], n_frozen=len(fz),
                         frozen=[dict(name=z['name'], ticks=z['last']-z['first'], d0=z['d0'], hp0=z.get('hp0'), hp1=z.get('hp1'),
                                      slow=[s[2] for s in slow.get(g, [])][:1]) for g, z in fz.items()],
                         near_not_frozen=len(near[cg]-set(fz))))
Path(__file__).with_name('live_freeze.json').write_text(json.dumps(rows, indent=0))
L = [r['life_ticks'] for r in rows]; F = [z['ticks'] for r in rows for z in r['frozen']]; D = [z['d0'] for r in rows for z in r['frozen'] if z['d0'] is not None]
print('cubes', len(rows), 'captures', len({r['capture'] for r in rows}), 'frame dt', st.median([r['frame_dt'] for r in rows if r['frame_dt']]))
print('cube life ticks: median', st.median(L), 'deciles', [round(x) for x in st.quantiles(L, n=10)])
print('cube took damage (hp_min < max):', sum(r['cube_hp_min'] < r['cube_max_hp'] for r in rows), '; hp_last <= 0 or < max at end:', sum(r['cube_hp_last'] < r['cube_max_hp'] for r in rows))
print('frozen per cube: mean', round(st.mean([r['n_frozen'] for r in rows]), 2), 'zero-frozen cubes', sum(r['n_frozen'] == 0 for r in rows))
print('freeze ticks per body: median', st.median(F), 'deciles', [round(x) for x in st.quantiles(F, n=10)])
print('frozen body distance to cube (tiles): median', round(st.median(D), 2), 'max', round(max(D), 2), 'share > 2.5', round(sum(d > 2.5 for d in D)/len(D), 3))
print('enemies within 2.5 of cube never frozen per cube: mean', round(st.mean([r['near_not_frozen'] for r in rows]), 2))
S = [s for r in rows for z in r['frozen'] for s in z['slow']]
print('after-slow durations', sorted(set(S)), 'bodies with after-slow', len(S), 'of', len(F))
