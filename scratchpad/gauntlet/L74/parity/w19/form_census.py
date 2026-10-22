"""FORMATION CENSUS (W19): where do the members of an own multi-unit play stand live vs where the fork lays them for the same
tap? Live: the play's tap (the harness's point: the confirmation's intended) and its members' positions on their first frame
(deploying, before any move). SIM: the same card played at the same tap on an empty board (towers up, levels 16), member
positions one tick later (Battle.step). Members are matched one-to-one by nearest. Per card: member error distribution and
the mean signed error by tap column (does the SIM shift the ring?).
  python form_census.py LIVE_DIR [GLOB] [--cards Skeletons]    (PARITY_SIM_PATH)"""
import glob
import itertools
import json
import os
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402

catalog, _ = load_catalog()
args = [a for a in sys.argv[1:] if not a.startswith('--')]
cards = set(sys.argv[sys.argv.index('--cards') + 1].split(',')) if '--cards' in sys.argv else {'Skeletons'}
d, g = Path(args[0]), args[1] if len(args) > 1 else 'live_play_*.jsonl'
eng = F.Engine(); b = eng.b
cache = {}


def sim_layout(card, side, x, y):
    key = (card, side, x, y)
    if key not in cache:
        cid = eng.ids[card]
        b.reset(1, [[cid], [cid]], 0, 200, None, [[7728, 4858, 4858], [7728, 4858, 4858]], [], levels=[[16], [16]], tower_levels=[16, 16])
        before = json.loads(b.save()); after = json.loads(json.dumps(before))
        after['players'][side]['mana'] = after['calib']['max_mana'] * after['mana_unit']
        load_edited(b, before, after)
        slot = next((i for i, c in enumerate(json.loads(b.save())['players'][side]['hand']) if c != F.NO_CARD), 0)
        b.step([(side, slot, round(x * 18), round(y * 18))], 0)
        b.step([], 1)
        _, bodies = eng.bodies({})
        cache[key] = [(bd['x'], bd['y']) for bd in bodies if not bd['tower'] and bd['side'] == side]
    return cache[key]


err = defaultdict(Counter); shift = defaultdict(lambda: [0, 0, 0]); EX = []
for p in sorted(glob.glob(str(d / g))):
    m, why = F.read_match(p)
    if m is None:
        continue
    tr = F.tracks(m['frames'])
    used = set()
    for pl in m['plays']:
        if pl['name'] not in cards:
            continue
        cands = [r for r in tr.values() if r['side'] == m['side'] and (catalog.get(r['card_id']) or {}).get('display_name') == pl['name']
                 and pl['tick'] <= r['first'] <= pl['tick'] + 80 and r['id'] not in used]
        if not cands:
            continue
        t1 = min(r['first'] for r in cands)
        grp = [r for r in cands if r['first'] <= t1 + 2]
        used.update(r['id'] for r in grp)
        live = [(r['x'], r['y']) for r in grp]
        sim = sim_layout(pl['name'], m['side'], pl['x'], pl['y'])
        if len(live) != len(sim) or not live:
            err[pl['name']]['count_mismatch'] += 1
            continue
        best = min(itertools.permutations(range(len(sim))), key=lambda pm: sum(math.hypot(live[i][0] - sim[j][0], live[i][1] - sim[j][1]) for i, j in enumerate(pm)))
        col = 'left half' if pl['x'] < 9000 else 'right half'
        EX.append(dict(match=Path(p).stem, side=m['side'], tap=(pl['x'], pl['y']), live=live, sim=[sim[j] for j in best], elixir=pl.get('elixir'), tick=pl['tick'], first=t1, xy=pl['xy']))
        for i, j in enumerate(best):
            e = math.hypot(live[i][0] - sim[j][0], live[i][1] - sim[j][1])
            err[pl['name']][min(int(e // 20) * 20, 300)] += 1
            s = shift[(pl['name'], col, 'own side bottom' if m['side'] == 0 else 'own side top')]
            s[0] += 1; s[1] += sim[j][0] - live[i][0]; s[2] += sim[j][1] - live[i][1]
for k, c in err.items():
    n = sum(v for b_, v in c.items() if b_ != 'count_mismatch')
    print(k, 'members', n, 'error bins (20 mt):', sorted((b_, v) for b_, v in c.items() if b_ != 'count_mismatch'), 'count mismatch', c['count_mismatch'])
for k, (n, sx, sy) in sorted(shift.items()):
    print(k, 'members', n, 'mean SIM-live dx %.1f dy %.1f' % (sx / n, sy / n))
if os.environ.get('FORM_JSON'):
    json.dump(EX, open(os.environ['FORM_JSON'], 'w'))
