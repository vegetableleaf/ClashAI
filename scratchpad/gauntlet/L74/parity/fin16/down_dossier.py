"""down_dossier.py BASE_DIR ARM_DIR OUT.json: for every J1 strict fight that MOVES between two runs (base fin15, arm fin16:
cmpci.py's keys), what changed between the two SIMs. Exact, from the runs' own fight records (no re-run):
  - the fight's plays, and which of them are cards the 10-19 update changed (PATCH1019.md section 1);
  - the set-up bodies (alive at t0) of changed cards;
  - the EARLIEST-born body whose SIM record differs between the arms (sim death / positions / hp / deploy / pairing): where
    fin16 first departs from fin15 inside the fight, and whether that body is a changed card itself (direct) or not (knock-on);
  - the card view (live / base sim / arm sim): which deaths / tower value carried the verdict.
Prints a summary by direction (down / up) and mechanism; writes every moved fight to OUT.json."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

# PATCH1019.md section 1 (engine names): Skeletons + evo (SummonRadius), Dart Goblin, Cannon Cart, Minion Giant, Rune Giant,
# Electro Dragon, Flying Machine, Void, Skeleton Barrel + evo; the 10-19 table also takes Hero E-Wiz attack_start_delay 500 -> 0.
CHANGED = {'Skeletons', 'BlowdartGoblin', 'MovingCannon', 'MinionGiant', 'GiantBuffer', 'RuneGiant', 'ElectroDragon',
           'DartBarrell', 'DarkMagic', 'SkeletonBalloon', 'SkeletonContainer'}
HERO_EWIZ = ('ElectroWizard', 2)
FORM = ('', ' evo', ' hero')
FIELDS = ('paired', 'sim_death', 'pos_first', 'pos_med', 'pos_end', 'hp_med', 'hp_signed_end', 'deploy_sim')


def changed(name, form):
    return name in CHANGED or (name, form) == HERO_EWIZ


def load(d):
    out = {}
    for p in sorted((Path(d) / 'matches').glob('*.json')):
        m = json.loads(p.read_text(encoding='utf-8'))
        if m['summary'].get('skipped') or not m['summary'].get('phase3b_births'):
            continue
        for r in m.get('fights', []):
            if 'error' in r or not F.is_clean(r, 'strict'):
                continue
            s = F.card_scores(r)
            if s is None:
                continue
            a = r['anchor']
            k = (m['summary']['match'][10:], r['t0'], a['tick'], ('own ' if r['own'] else 'opp ') + a['name'] + FORM[a['form']])
            out[k] = (s['aK'], r, m['summary']['side'])
    return out


def lab(bd, obs):
    return ('own ' if bd['side'] == obs else 'opp ') + bd['name'] + FORM[bd.get('form', 0)]


def study(ra, rb, obs):
    ev = [(e['tick'] - rb['t0'], 'own' if e['side'] == obs else 'opp', e['name'] + FORM[e.get('form', 0)])
          for e in rb['events'] if e.get('kind') == 'play']
    ev_changed = [e for e, x in zip(ev, (x for x in rb['events'] if x.get('kind') == 'play')) if changed(x['name'], x.get('form', 0))]
    setup_changed = sorted({lab(b, obs) for b in rb['bodies'] if b.get('setup') and changed(b['name'], b.get('form', 0))})
    key = lambda b: (b['name'], b.get('form', 0), b['side'], b.get('born'), b.get('setup'))
    A = {}
    for b in ra['bodies']:
        A.setdefault(key(b), []).append(b)
    first, ndiff = None, 0
    for b in sorted(rb['bodies'], key=lambda b: (b.get('born') if b.get('born') is not None else -1)):
        lst = A.get(key(b))
        a = lst.pop(0) if lst else None
        diff = [f for f in FIELDS if (a or {}).get(f) != b.get(f)] if a else ['only_in_arm']
        if diff:
            ndiff += 1
            if first is None:
                first = dict(body=lab(b, obs), born=None if b.get('born') is None else b['born'] - rb['t0'], setup=b.get('setup'),
                             changed_card=changed(b['name'], b.get('form', 0)), fields=diff,
                             base={f: (a or {}).get(f) for f in diff}, arm={f: b.get(f) for f in diff})
    gone = sum(len(v) for v in A.values())                 # bodies only in base
    if first is None and gone:
        first = dict(body='only_in_base', changed_card=None, fields=['only_in_base'])
    return dict(plays=ev, plays_changed=ev_changed, setup_changed=setup_changed, first_sim_diff=first, bodies_differing=ndiff,
                only_in_base=gone, card_live=rb['card']['live'], card_base=ra['card']['sim'][0], card_arm=rb['card']['sim'][0],
                towers_arm=rb['towers'])


def mech(x):
    f = x['first_sim_diff']
    if f is None:
        return 'no body differs (tower / timing only)'
    sk = any(e[2].startswith('Skeletons') for e in x['plays_changed']) or any('Skeletons' in s for s in x['setup_changed'])
    if f.get('changed_card'):
        return 'direct: ' + f['body'].split(' ', 1)[1].replace(' evo', '') + (' (set-up)' if f.get('setup') else '')
    if sk:
        return 'knock-on of Skeletons'
    if x['plays_changed'] or x['setup_changed']:
        return 'knock-on of another changed card'
    return 'no changed card in the fight'


def main(base, arm, out):
    A, B = load(base), load(arm)
    res = []
    for k in sorted(set(A) & set(B)):
        if A[k][0] == B[k][0]:
            continue
        x = study(A[k][1], B[k][1], B[k][2])
        x.update(key=f'{k[0]}@{k[1]} {k[3]}', anchor=k[3], dir='down' if B[k][0] < A[k][0] else 'up', mech=mech(x))
        res.append(x)
    Path(out).write_text(json.dumps(res, indent=1))
    for d in ('down', 'up'):
        r = [x for x in res if x['dir'] == d]
        print(f'== {d}: {len(r)} fights')
        for m, n in Counter(x['mech'] for x in r).most_common():
            print(f'  {n:4d}  {m}')
        print('  anchors:', Counter(x['anchor'] for x in r).most_common(12))
        print('  first differing body:', Counter((x['first_sim_diff'] or {}).get('body') for x in r).most_common(10))
        print('  first differing field:', Counter(tuple((x['first_sim_diff'] or {}).get('fields', ())) for x in r).most_common(6))


if __name__ == '__main__':
    main(*sys.argv[1:4])
