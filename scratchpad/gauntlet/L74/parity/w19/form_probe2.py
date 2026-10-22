"""Where does the fork actually stand a Blue Skeletons play (normal deploy, Battle.step) vs formation_preview, and which lane
does each member walk to? Taps of the L16-era lane-flip fights.   python form_probe2.py  (PARITY_SIM_PATH)"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402
eng = F.Engine(); b = eng.b; S = eng.ids['Skeletons']
for x, y in ((8500, 533), (8500, 10500), (8530, 10500), (8470, 10500)):
    b.reset(1, [[S], [S]], 0, 200, None, [[7728, 4858, 4858], [7728, 4858, 4858]], [], levels=[[16], [16]], tower_levels=[16, 16])
    before = json.loads(b.save()); after = json.loads(json.dumps(before))
    after['players'][0]['mana'] = after['calib']['max_mana'] * after['mana_unit']
    load_edited(b, before, after)
    prev = b.formation_preview(0, 'Skeletons', x * 18, y * 18)
    slot = next((i for i, c in enumerate(json.loads(b.save())['players'][0]['hand']) if c != F.NO_CARD), 0)
    r = b.step([(0, slot, x * 18, y * 18)], 0)[0]
    st0, bod0 = eng.bodies({})
    print('   t+0', [(bd['x'], bd['y']) for bd in bod0 if not bd['tower'] and bd['side'] == 0])
    track = []
    for t in range(1, 60):
        b.step([], 1)
        if t in (1, 2, 30, 59):
            st, bodies = eng.bodies({})
            track.append((t, [(bd['x'], bd['y']) for bd in bodies if not bd['tower'] and bd['side'] == 0]))
    print((x, y), sim_reason := eng.sim.DEPLOY_REASONS[r[1]], 'preview', [(round(px / 18), round(py / 18)) for _, px, py, _ in prev])
    for t, pts in track:
        print('   t+%d' % t, pts)
