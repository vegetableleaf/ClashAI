"""Live attack-progress step and walk speed under Ice Wizard buffs, from phase-3 captures (local, git-ignored dirs).

Usage: python live_p3.py <capture dir> [...]
Field meanings: L74/parity/reader_val/validate_p3.py (phase3.bodies[].attack.progress_raw counts up in game ms;
phase2.units[].buffs carry name / remaining / config multipliers). Prints derived numbers only.

STEP: for every attacker and every pair of consecutive samples (gap <= 3 ticks) with the same target, the same buff-name
set on both samples, and progress_raw > 0 on the first: step = (progress1 - progress0) / gap, kept when it is an integer
in [0, 100]. Classed by the IceWizard buff present (a body under none of them and no other buff = 'unbuffed').
WALK: per-tick displacement (millitiles) of every body on moving samples, same classes, per card and pooled ratio.
"""
import json
import math
import sys
from collections import Counter, defaultdict

ORDER = ('IceWizardHero_FreezeBuff', 'IceWizardHero_FreezeBuff_dummy', 'IceWizardHero_SlowBuff', 'IceWizardHeroSlow',
         'IceWizardHeroCold', 'IceWizardSlowDown', 'IceWizardCold')


def klass(buffs):
    names = {b['name'] for b in buffs or []}
    for n in ORDER:
        if n in names:
            return n
    return 'unbuffed' if not names else 'other:' + '+'.join(sorted(names))


def frames(d):
    with open(f'{d}/frames.jsonl', encoding='utf-8') as f:
        for line in f:
            j = json.loads(line)
            if j.get('battle_active') and (j.get('phase3') or {}).get('valid') and (j.get('phase2') or {}).get('valid'):
                yield j


def main(d):
    steps = defaultdict(Counter)          # class -> Counter(step)
    seq = defaultdict(Counter)            # class -> Counter(seq_idx at f0) for kept intervals
    who = defaultdict(Counter)            # class -> Counter(attacker name)
    walk = defaultdict(lambda: defaultdict(list))   # class -> name -> [v]
    cfg = {}
    prev = None
    for j in frames(d):
        t = j['game_tick']
        units = {u['generation']: u for u in j['phase2']['units']}
        pos = {e['category']: (e['x'], e['y']) for e in j['entities'] if 'x' in e}
        att = {b['generation']: b['attack'] for b in j['phase3']['bodies']}
        for u in units.values():
            for b in u.get('buffs') or []:
                if b['name'].startswith('IceWizard'):
                    cfg[b['name']] = (b['duration_ms_raw'], b['config'].get('SpeedMultiplier'), b['config'].get('HitSpeedMultiplier'))
        if prev:
            t0, units0, pos0, att0 = prev
            dt = t - t0
            if 0 < dt <= 3:
                for g, u in units.items():
                    u0 = units0.get(g)
                    if not u0:
                        continue
                    k0, k1 = klass(u0.get('buffs')), klass(u.get('buffs'))
                    if k0 != k1 or {b['name'] for b in u0.get('buffs') or []} != {b['name'] for b in u.get('buffs') or []}:
                        continue
                    a0, a1 = att0.get(g), att.get(g)
                    if a0 and a1 and a0['target_gen'] not in (None, 'unlisted') and a0['target_gen'] == a1['target_gen'] \
                            and a0['progress_raw'] > 0:
                        dp = a1['progress_raw'] - a0['progress_raw']
                        if dp >= 0 and dp % dt == 0 and dp // dt <= 100:
                            steps[k1][dp // dt] += 1
                            seq[k1][a0['seq_idx']] += 1
                            who[k1][u['name']] += 1
                    if g in pos and g in pos0:
                        v = math.hypot(pos[g][0] - pos0[g][0], pos[g][1] - pos0[g][1]) / dt
                        if v > 0:
                            walk[k1][u['name']].append(v)
        prev = (t, units, pos, att)
    print('==', d.rstrip('/').rsplit('/', 1)[-1])
    for n, c in sorted(cfg.items()):
        print(f'  BUFF {n}: duration {c[0]} ms, SpeedMultiplier {c[1]}, HitSpeedMultiplier {c[2]}')
    for k in sorted(steps, key=lambda k: (k.startswith('other'), k)):
        print(f'  STEP {k}: n={sum(steps[k].values())} steps {dict(steps[k].most_common(6))} seq_idx {dict(seq[k])} '
              f'attackers {dict(who[k].most_common(6))}')
    med = lambda v: sorted(v)[len(v) // 2] if v else None  # noqa: E731
    base = walk['unbuffed']
    for k in ORDER:
        rows = [(n, med(v), med(base.get(n, [])), len(v)) for n, v in walk[k].items() if base.get(n) and len(v) >= 3]
        if rows:
            print(f'  WALK {k}: ' + '; '.join(f'{n} {s:.1f}/{b:.1f}={s / b:.3f} (n={c})' for n, s, b, c in rows))


if __name__ == '__main__':
    for d in sys.argv[1:]:
        main(d)
