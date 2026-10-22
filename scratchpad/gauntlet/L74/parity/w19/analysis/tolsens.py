"""Tolerance sensitivity of the J1 failures (characterisation only; the owner metric stays DEATH_TOL 10 / tower max(100, 10%)):
how many failing fights pass if deaths may differ by 15 / 20 / 30 ticks, or towers by 2x the tolerance, or one more body may miss.
  python tolsens.py RUN_DIR"""
import glob, json, os, sys
from collections import Counter
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

fails = []
n = 0
for p in sorted(glob.glob(sys.argv[1] + '/matches/*.json')):
    d = json.load(open(p, encoding='utf-8'))
    if d['summary'].get('skipped') or not d['summary'].get('phase3b_births'):
        continue
    for r in d['fights']:
        c = r.get('card')
        if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
            continue
        n += 1
        if not F.card_agree(c['live'], c['sim'][0])[0]:
            fails.append(c)
print('strict fights', n, 'failing', len(fails))
base = (F.DEATH_TOL, F.TOWER_FLOOR, F.TOWER_REL, F.SWARM_SLACK)
for name, (dt, tf, tr, sl) in {'death 15': (15, 100, .1, .1), 'death 20': (20, 100, .1, .1), 'death 30': (30, 100, .1, .1),
                               'death 60': (60, 100, .1, .1), 'tower x2': (10, 200, .2, .1),
                               'death 20 + tower x2': (20, 200, .2, .1), 'swarm slack .25': (10, 100, .1, .25)}.items():
    F.DEATH_TOL, F.TOWER_FLOOR, F.TOWER_REL, F.SWARM_SLACK = dt, tf, tr, sl
    ok = sum(F.card_agree(c['live'], c['sim'][0])[0] for c in fails)
    print(f'{name:22s}: {ok} of {len(fails)} failing fights pass ({ok/len(fails):.2f}); raw would be {(n - len(fails) + ok)/n:.4f}')
F.DEATH_TOL, F.TOWER_FLOOR, F.TOWER_REL, F.SWARM_SLACK = base
