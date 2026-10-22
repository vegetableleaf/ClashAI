"""Does an Ice Wizard slow stretch a SPAWNER's cycle? (W19 lead: the SIM's Witch waves come 14 ticks early in slowed fights.)
LIVE: every Witch-type spawner track (Witch, Tombstone, Furnace, huts) -> its waves (children of its card, smaller max_hp,
first seen within 3.5 tiles, clustered within 6 ticks) -> the interval between consecutive waves and the ticks of it during
which the spawner carried an Ice Wizard slow (phase-2 buff rows, PARITY_BUFFS). SIM: a lone red spawner, waves timed with
and without an Ice Wizard slow re-applied every tick.
  python witch_slow.py live LIVE_DIR [GLOB]   (PARITY_BUFFS=chunk buffs.json)      python witch_slow.py sim"""
import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402

SPAWNERS = {'Witch': 140, 'Tombstone': 70, 'FirespiritHut': 100, 'GoblinHut': 44, 'BarbarianHut': 280}   # table cycle, ticks
SLOWS = ('IceWizardSlowDown', 'IceWizardCold', 'IceWizardHero_SlowBuff', 'IceWizardHeroSlow', 'IceWizardHeroCold')

if sys.argv[1] == 'live':
    catalog, _ = load_catalog()
    out = defaultdict(list)
    for p in sorted(glob.glob(str(Path(sys.argv[2]) / (sys.argv[3] if len(sys.argv) > 3 else 'live_play_*.jsonl')))):
        m, why = F.read_match(p)
        if m is None or not m['ext']:
            continue
        buffs = F.phase2_buffs(p)
        tr = list(F.tracks(m['frames']).values())
        gen_of = {}
        for t, bodies in m['frames']:
            for b in bodies:
                if b.get('gen') is not None:
                    gen_of.setdefault(b['id'], b['gen'])
        for par in tr:
            name = (catalog.get(par['card_id']) or {}).get('display_name')
            if name not in SPAWNERS:
                continue
            kids = sorted(r['first'] for r in tr if r['card_id'] == par['card_id'] and r['side'] == par['side'] and r['id'] != par['id']
                          and r['max_hp'] < .9 * par['max_hp'] and par['first'] < r['first'] <= par['last'] + 2
                          and math.hypot(r['x'] - par['x'], r['y'] - par['y']) < 9000)
            waves = []
            for k in kids:
                if not waves or k - waves[-1] > 6:
                    waves.append(k)
            g = gen_of.get(par['id'])
            for a, b in zip(waves, waves[1:]):
                slowed = sum(1 for t, u in buffs.items() if a <= t < b and g in u and any(n in SLOWS for n, _ in u[g]))
                frames = sum(1 for t in buffs if a <= t < b)
                out[name].append((b - a, slowed / frames if frames else None))
    for name, v in out.items():
        clean = Counter(d for d, s in v if s == 0)
        slow = [(d, s) for d, s in v if s]
        print(f'{name}: intervals {len(v)}; unslowed modal {clean.most_common(4)}; slowed n {len(slow)}, '
              f'median interval {sorted(d for d, _ in slow)[len(slow)//2] if slow else None}; examples {sorted(slow)[:12]}')
        bins = defaultdict(list)
        for d, s in slow:
            bins[round(s * 4) / 4].append(d)
        print('   by slowed share of the interval:', {k: (len(x), sorted(x)[len(x)//2]) for k, x in sorted(bins.items())})
else:
    from scratchpad.gauntlet.L74.parity.mechanics import load_edited
    eng = F.Engine(); b = eng.b; slow = eng.slow_ids().get('base')
    print('IW base slow buff id', slow)
    for name in SPAWNERS:
        if name not in eng.ids:
            continue
        for slowed in (False, True):
            b.reset(1, [[eng.ids['Knight']], [eng.ids[name]]], 0, 200, None, [[4824, 0, 0], [4824, 0, 0]],
                    [(1, eng.ids[name], 9000 * 18, 24000 * 18, -1)], levels=[[15], [15]], tower_levels=[15, 15])
            E = json.loads(b.save())['ents']
            i = next(j for j in range(len(E['alive'])) if E['alive'][j] and E['kind'][j] not in ('KingTower', 'PrincessTower'))
            seen = {j for j in range(len(E['alive'])) if E['alive'][j]}
            births = []
            for t in range(1, 700):
                if slowed and slow is not None:
                    before = json.loads(b.save()); after = json.loads(json.dumps(before)); EE = after['ents']
                    n = len(EE['alive']); sl = len(EE['buffs']) // n
                    mine = [k for k in range(i * sl, (i + 1) * sl) if EE['buffs'][k]['id'] == slow]
                    if mine:
                        EE['buffs'][mine[0]]['ms'] = 2500
                    else:
                        F.set_buff(EE, i, slow, 2500)
                    load_edited(b, before, after)
                b.step([], 1)
                E = json.loads(b.save())['ents']
                new = [j for j in range(len(E['alive'])) if E['alive'][j] and j not in seen and E['spawned_by'][j] is not None]
                seen |= {j for j in range(len(E['alive'])) if E['alive'][j]}
                if new:
                    births.append(t)
                if not E['alive'][i]:
                    break
            waves = []
            for k in births:
                if not waves or k - waves[-1] > 6:
                    waves.append(k)
            print(f'{name} slowed={slowed}: waves at {waves[:6]}; intervals {[b_ - a for a, b_ in zip(waves, waves[1:])][:5]}')
