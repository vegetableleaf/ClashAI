"""Live pocket depth: opponent TROOP plays (fights.deployments, first-seen point; diggers and spells left out) made while
exactly one / both of OUR princesses are down, by lane (fallen / standing) and depth past the river centre (tiles), plus
the SIM's deploy boundary probed tile by tile in the fallen lane. W18 leftover + the pocket-depth rule.
  python pocket_live.py LIVE_DIR [GLOB]"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402
from scratchpad.gauntlet.L74.parity.w19.king_pocket import falls  # noqa: E402

catalog, _ = load_catalog()
d, g = Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'live_play_*.jsonl'
lane, depth = Counter(), Counter()
for p in sorted(glob.glob(str(d / g))):
    m, why = F.read_match(p)
    if m is None:
        continue
    fl = falls(p, m['side'])
    if not fl:
        continue
    ky = next((bd['y'] for bd in m['frames'][0][1] if bd['tower'] and bd['side'] == m['side'] and bd['id'].endswith('K')), None)
    if ky is None:
        continue
    bottom = ky < 16000
    ev, _ = F.deployments(m, catalog)
    for e in ev:
        if e['kind'] != 'play' or e['side'] == m['side'] or 'x' not in e or e.get('dig') or e.get('spell_spawned'):
            continue
        c = next((c for c in catalog.values() if c['display_name'] == e['name']), {})
        if c.get('type') == 'spell' or e['name'] in F.DIGGERS:
            continue
        down = {k for k, t in fl.items() if t <= e['tick']}
        if not down:
            continue
        past = (16000 - e['y']) if bottom else (e['y'] - 16000)      # mt past the river centre into OUR half
        if past <= 1000:
            continue
        side_l = 'L' if e['x'] < 9000 else 'R'
        # our 'L' princess is the one at x < 9000 in frame coordinates
        tag = 'both down' if len(down) == 2 else ('fallen lane' if side_l in down else 'STANDING lane')
        lane[tag] += 1
        depth[tag, round(past / 1000)] += 1
print('opponent troop plays > 1 tile past the river into our half, by lane:', dict(lane))
for tag in ('fallen lane', 'STANDING lane', 'both down'):
    print(tag, 'depth (tiles past the river centre):', sorted((k[1], v) for k, v in depth.items() if k[0] == tag))
eng = F.Engine(); b = eng.b; sim = eng.sim
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402
K = eng.ids['Knight']
row = []
for y in range(16500, 26001, 500):
    b.reset(1, [[K], [K]], 0, 200, None, [[4824, 3052, 3052], [4824, 0, 3052]], [], levels=[[15], [15]], tower_levels=[15, 15])
    before = json.loads(b.save()); after = json.loads(json.dumps(before))
    after['players'][0]['mana'] = after['calib']['max_mana'] * after['mana_unit']
    load_edited(b, before, after)
    slot = next((i for i, c in enumerate(json.loads(b.save())['players'][0]['hand']) if c != F.NO_CARD), 0)
    r = b.step([(0, slot, round(3500 * 18), round(y * 18))], 0)[0]
    row.append(f'{(y - 16000) / 1000:.1f}:{sim.DEPLOY_REASONS[r[1]][:3]}')
print('SIM, Red left princess down, Blue Knight at x 3.5 tiles, tiles past the river centre:', ' '.join(row))
