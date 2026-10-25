"""Q2 (SIM vs live) + Q3 (redirect) on replay_metrics 'fights' outputs, joined with the live census.
Same live situation in both engines: the SIM is rebuilt from the live board at the frame before the fight's anchor play and
every live play in the window is replayed (our Tornado at its live tick and point).
  Q2: J3 own-king windows whose live trigger is a king DAMAGE hit with our own Tornado in the 80 ticks before it.
      Per window (as the J3 score) and per distinct live wake, judged on the window anchored on our Tornado itself
      (t0 = the frame before the cast: the cleanest 'same situation' test).
  Q3: fights anchored on our Tornado, our king asleep and both our princesses up at t0 (census): enemy damage on our king vs
      our princesses over the fight window, live vs SIM, paired; bootstrap CI by match.
Read-only.   python q23_replay.py CENSUS.json MATCHES_DIR [MATCHES_DIR ...]"""
import glob
import json
import os
import random
import sys
from collections import Counter, defaultdict

BT = ('HogRider', 'RoyalHogs', 'BattleRam', 'Giant', 'RoyalGiant', 'Golem', 'ElixirGolem', 'GoblinGiant', 'ElectroGiant',
      'Balloon', 'LavaHound', 'RamRider', 'SkeletonBalloon', 'GoblinBarrel')


def load(census, dirs):
    cen = {m['match']: m for m in json.load(open(census))['matches'] if 'king' in m}
    j3w, q3 = [], []
    for d_ in dirs:
        for f in sorted(glob.glob(d_ + '/*.json')):
            stem = os.path.basename(f)[:-5]
            c = cen.get(stem)
            d = json.load(open(f))
            if c is None or not d.get('fights'):
                continue
            ok = next(k for k in c['king'] if k['side'] == 'own')
            for fi in d['fights']:
                jm = fi.get('jm') or {}
                for r in jm.get('j3') or []:
                    if r.get('tornado') and r['side'] == 'own' and r['cause'] == 'damage':
                        acts = ok['activators'] if ok.get('trigger') is not None and abs(ok['trigger'] - r['live']) <= 3 else []
                        j3w.append(dict(m=stem, t0=fi['t0'], anchor=fi['anchor']['name'] if fi.get('own') else 'opp',
                                        live=r['live'], sim=r['sim'], agree=r['agree'], acts=[a[4:] for a in acts]))
                a = fi['anchor']
                if not (fi.get('own') and a['name'] == 'Tornado'):
                    continue
                asleep = ok.get('trigger') is None or ok['trigger'] >= fi['t0']
                both = ok.get('down') is None or ok['down'] > fi['t0']
                if not (asleep and both):
                    continue
                if 'towers' not in fi:      # an unreplayed fight (error / skipped) carries no tower damage
                    continue
                s, tw = a['side'], fi['towers']
                g = lambda k, w: tw.get(f'T{s}{k}', {}).get(w, 0)
                vic = sorted({v['victim'][4:] for v in jm.get('j2') or [] if v.get('spell') == 'Tornado' and v['victim'].startswith('opp ')})
                q3.append(dict(m=stem, t0=fi['t0'], vic=vic, lk=g('K', 'live'), sk=g('K', 'sim'),
                               lp=g('L', 'live') + g('R', 'live'), sp=g('L', 'sim') + g('R', 'sim')))
    return j3w, q3


def share(rs, k, p):
    return sum(r[k] for r in rs) / max(1, sum(r[k] + r[p] for r in rs))


def boot_diff(rs, B=2000):
    ms = sorted({r['m'] for r in rs})
    by = defaultdict(list)
    for r in rs:
        by[r['m']].append(r)
    rng, out = random.Random(0), []
    for _ in range(B):
        pick = [r for m in (rng.choice(ms) for _ in ms) for r in by[m]]
        out.append(share(pick, 'sk', 'sp') - share(pick, 'lk', 'lp'))
    out.sort()
    return out[int(.025 * B)], out[int(.975 * B) - 1]


def main():
    j3w, q3 = load(sys.argv[1], sys.argv[2:])
    print(f'Q2. J3 own-king windows, live trigger = king damage after our own Tornado: {len(j3w)} windows, '
          f'{len({(r["m"], r["live"]) for r in j3w})} distinct live wakes, {len({r["m"] for r in j3w})} matches')
    cat = Counter('agree' if r['agree'] else 'live-only (SIM king not woken)' if r['sim'] is None else 'both, > 10 ticks apart'
                  for r in j3w)
    print('  per window:', dict(cat), f"-> agree {cat['agree'] / max(1, len(j3w)):.3f}")
    ev = defaultdict(list)
    for r in j3w:
        ev[(r['m'], r['live'])].append(r)
    cl, by_act, offs = Counter(), defaultdict(Counter), []
    for rs in ev.values():
        rt = [r for r in rs if r['anchor'] == 'Tornado']
        if not rt:
            cl['no window anchored on the Tornado'] += 1
            continue
        r = max(rt, key=lambda r: r['t0'])
        k = 'agree' if r['agree'] else 'live-only' if r['sim'] is None else 'off'
        if k == 'off':
            offs.append(r['sim'] - r['live'])
        cl[k] += 1
        for a in set(r['acts']) or {'(no enemy in reach)'}:
            by_act[a][k] += 1
    print('  per distinct wake, replay starting on our Tornado cast:', dict(cl), 'off by (SIM - live ticks):', sorted(offs))
    n = cl['agree'] + cl['live-only'] + cl['off']
    print(f"    -> SIM reproduces the Tornado-to-king activation (trigger within 10 ticks): {cl['agree']}/{n} = "
          f"{cl['agree'] / max(1, n):.3f} (positives only: a SIM-only wake cannot appear in this slice)")
    for a, cc in sorted(by_act.items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        print(f'    activator {a:22s} {dict(cc)}')
    print(f'\nQ3. fights anchored on our Tornado, our king asleep + both princesses up at t0: {len(q3)} fights, '
          f'{len({r["m"] for r in q3})} matches')
    hit = Counter(('king hit live' if r['lk'] else 'not live') + ' / ' + ('king hit SIM' if r['sk'] else 'not SIM') for r in q3)
    print('  king damaged in the window:', dict(hit))
    lo, hi = boot_diff(q3)
    print(f"  king share of the enemy damage on our towers: live {share(q3, 'lk', 'lp'):.3f}, SIM {share(q3, 'sk', 'sp'):.3f}; "
          f"SIM - live {share(q3, 'sk', 'sp') - share(q3, 'lk', 'lp'):+.3f} [{lo:+.3f}, {hi:+.3f}] (match bootstrap)")
    tot = {k: sum(r[k] for r in q3) for k in ('lk', 'sk', 'lp', 'sp')}
    print(f"  totals hp: king live {tot['lk']} SIM {tot['sk']} (SIM/live {tot['sk'] / max(1, tot['lk']):.2f}); "
          f"princesses live {tot['lp']} SIM {tot['sp']} (SIM/live {tot['sp'] / max(1, tot['lp']):.2f})")
    for lab, sel in (('building-targeter or Goblin Barrel victim', lambda r: any(v.split(' ')[0] in BT for v in r['vic'])),
                     ('Hog Rider victim', lambda r: any(v.startswith('HogRider') for v in r['vic'])),
                     ('Goblin Barrel goblins victim', lambda r: any(v.startswith('GoblinBarrel') for v in r['vic'])),
                     ('no building-targeter victim', lambda r: not any(v.split(' ')[0] in BT for v in r['vic']))):
        rs = [r for r in q3 if sel(r)]
        if not rs:
            continue
        h = Counter((bool(r['lk']), bool(r['sk'])) for r in rs)
        lo, hi = boot_diff(rs)
        print(f"  {lab:42s} n {len(rs):3d}: king share live {share(rs, 'lk', 'lp'):.3f} SIM {share(rs, 'sk', 'sp'):.3f} "
              f"(SIM - live [{lo:+.3f}, {hi:+.3f}]); king hit both {h[(True, True)]}, live only {h[(True, False)]}, "
              f"SIM only {h[(False, True)]}, neither {h[(False, False)]}; king hp live {sum(r['lk'] for r in rs)} SIM "
              f"{sum(r['sk'] for r in rs)}, princess hp live {sum(r['lp'] for r in rs)} SIM {sum(r['sp'] for r in rs)}")


if __name__ == '__main__':
    main()
