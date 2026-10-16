"""Live truth for the Ice Wizard slow, from phase-2 capture frames (local, git-ignored capture dirs).

Usage: python live.py <capture dir> [<capture dir> ...]
Per capture, prints only derived numbers (no addresses or reader internals):
  1. every IceWizard* buff instance: name, victim, duration_ms_raw, config multipliers, decrement per tick;
  2. WALK: per victim body, the per-tick displacement (millitiles / tick) on frames where it moved, slowed vs unslowed;
  3. TOWER CADENCE: a crown tower's shot launches (new projectiles sourced at it), intervals while it carries an
     IceWizard slow vs not.
"""
import json
import math
import sys
from collections import defaultdict

SLOWS = ('IceWizardHeroSlow', 'IceWizardHeroCold', 'IceWizardHero_SlowBuff', 'IceWizardSlowDown', 'IceWizardCold')
FROZEN = ('IceWizardHero_FreezeBuff', 'Freeze')


def frames(d):
    with open(f'{d}/frames.jsonl') as f:
        for line in f:
            j = json.loads(line)
            if j.get('battle_active') and (j.get('phase2') or {}).get('valid'):
                yield j


def med(v):
    v = sorted(v)
    return round(v[len(v) // 2], 1) if v else None


def main(d):
    print('==', d.rsplit('/', 1)[-1])
    inst = {}                      # (body, buff name) -> [first tick, last tick, durations, first remaining, config]
    trail = defaultdict(list)      # body -> [(tick, x, y, slowed, frozen)]
    names = {}
    shots = defaultdict(list)      # tower body -> [(tick, slowed)]
    seen_proj = set()
    for j in frames(d):
        t = j['game_tick']
        pos = {e['address']: (e['x'], e['y']) for e in j['entities']}
        units = {u['address']: u for u in j['phase2']['units']}
        for a, u in units.items():
            names[a] = u['name']
            bs = u.get('buffs') or []
            slowed = any(b['name'] in SLOWS for b in bs)
            frozen = any(b['name'] in FROZEN for b in bs)
            for b in bs:
                if b['name'] and b['name'].startswith('IceWizard'):
                    k = (a, b['name'])
                    r = inst.setdefault(k, [t, t, set(), b['remaining_ms_raw'], b.get('config'), []])
                    r[1] = t
                    r[2].add(b['duration_ms_raw'])
                    r[5].append((t, b['remaining_ms_raw']))
            if a in pos:
                trail[a].append((t, *pos[a], slowed, frozen))
        for p in j.get('projectiles') or []:
            key = p['address'], p.get('generation_key')
            src = units.get(p.get('source'))
            if key in seen_proj or not src or src['name'] not in ('PrincessTower', 'KingTower'):
                continue
            seen_proj.add(key)
            sl = any(b['name'] in SLOWS for b in src.get('buffs') or [])
            shots[p['source']].append((t, sl))
    # 1. instances
    by_name = defaultdict(list)
    for (a, n), (t0, t1, durs, rem0, cfg, tr) in inst.items():
        dec = [(r0 - r1) / (s1 - s0) for (s0, r0), (s1, r1) in zip(tr, tr[1:]) if s1 > s0 and r1 < r0]
        by_name[n].append((names[a], sorted(durs), med(dec), cfg and {k: cfg[k] for k in ('SpeedMultiplier', 'HitSpeedMultiplier', 'SpawnSpeedMultiplier') if k in cfg}))
    for n, rows in by_name.items():
        print(f'  BUFF {n}: {len(rows)} body-instances; durations {sorted({x for r in rows for x in r[1]})}; '
              f'ms off per tick (median per body) {sorted({r[2] for r in rows}, key=str)}; config {rows[0][3]}; victims {sorted({r[0] for r in rows})}')
    # 2. walk
    walk = defaultdict(lambda: {True: [], False: []})
    for a, tr in trail.items():
        for (t0, x0, y0, s0, f0), (t1, x1, y1, s1, f1) in zip(tr, tr[1:]):
            if t1 <= t0 or t1 - t0 > 3 or f0 or f1 or s0 != s1:
                continue
            v = math.hypot(x1 - x0, y1 - y0) / (t1 - t0)
            if v > 0:
                walk[names[a]][s1].append(v)
    for n, w in sorted(walk.items()):
        if w[True]:
            ratio = (med(w[True]) / med(w[False])) if w[False] and med(w[False]) else None
            print(f'  WALK {n}: unslowed median {med(w[False])} mt/tick (n={len(w[False])}), slowed {med(w[True])} '
                  f'(n={len(w[True])}), ratio {ratio and round(ratio, 3)}')
    # 3. tower cadence
    for a, s in shots.items():
        iv = {True: [], False: []}
        for (t0, s0), (t1, s1) in zip(s, s[1:]):
            if s0 == s1 and t1 - t0 < 40:
                iv[s1].append(t1 - t0)
        if iv[True]:
            print(f'  TOWER {names[a]} shot intervals: unslowed {sorted(iv[False])}, slowed {sorted(iv[True])}')


if __name__ == '__main__':
    for d in sys.argv[1:]:
        main(d.rstrip('/'))
