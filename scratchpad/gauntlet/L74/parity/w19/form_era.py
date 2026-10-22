"""FORMATION x ERA CENSUS (lead 10-22: did the 10-19 update change other multi-unit layouts?). For every multi-unit play of
either side -- own plays at the tap, opponent plays at the harness's point (fights.deployments: the first-seen centroid) --
the live members' first-seen points vs the fork's layout of the same card at the same point (empty board, levels 16,
one tick after the command), members matched one-to-one. Per card and era (pre / post 10-19 10:00): members, median and
share > 60 mt of the member error.   python form_era.py LIVE_DIR [GLOB]   (PARITY_SIM_PATH)"""
import glob
import itertools
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402

catalog, _ = load_catalog()
d, g = Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'live_play_*.jsonl'
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
        r = b.step([(side, slot, round(x * 18), round(y * 18))], 0)[0]
        b.step([], 1)
        _, bodies = eng.bodies({})
        cache[key] = [(bd['x'], bd['y']) for bd in bodies if not bd['tower'] and bd['side'] == side] if eng.sim.DEPLOY_REASONS[r[1]] == 'OK' else None
    return cache[key]


err = defaultdict(list)
for p in sorted(glob.glob(str(d / g))):
    m, why = F.read_match(p)
    if m is None:
        continue
    era = 'post' if Path(p).stem[10:23] >= '20261019_1000' else 'pre'
    tr = F.tracks(m['frames'])
    ev, _ = F.deployments(m, catalog)
    for e in ev:
        if e['kind'] != 'play' or 'x' not in e or e.get('spell_spawned') or e.get('dig') or e['name'] not in eng.ids:
            continue
        cands = [r for r in tr.values() if r['side'] == e['side'] and (catalog.get(r['card_id']) or {}).get('display_name') == e['name']
                 and e['tick'] - 2 <= r['first'] <= e['tick'] + 80]
        if len(cands) < 2:
            continue
        t1 = min(r['first'] for r in cands)
        live = [(r['x'], r['y']) for r in cands if r['first'] <= t1 + 2]
        if not 2 <= len(live) <= 6:
            continue
        sim = sim_layout(e['name'], e['side'], e['x'], e['y'])
        if not sim or len(sim) != len(live):
            continue
        best = min(itertools.permutations(range(len(sim))), key=lambda pm: sum(math.hypot(live[i][0] - sim[j][0], live[i][1] - sim[j][1]) for i, j in enumerate(pm)))
        who = 'own' if e['side'] == m['side'] else 'opp'
        for i, j in enumerate(best):
            err[(e['name'], who, era)].append(math.hypot(live[i][0] - sim[j][0], live[i][1] - sim[j][1]))
print('card | side | era | members | median error mt | share > 60 mt')
for k in sorted(err):
    v = sorted(err[k])
    if len(v) >= 15:
        print(f'{k[0]} | {k[1]} | {k[2]} | {len(v)} | {v[len(v)//2]:.0f} | {sum(x > 60 for x in v)/len(v):.3f}')
import os
if os.environ.get('FERA_JSON'):
    json.dump({'|'.join(k): v for k, v in err.items()}, open(os.environ['FERA_JSON'], 'w'))
