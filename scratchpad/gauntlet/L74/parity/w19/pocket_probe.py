"""W18 leftover (W19 ledger): after ONE enemy princess falls, may a side deploy in the OTHER lane's pocket? Probe the engine's
deploy rule: Blue (side 0, bottom) plays a Knight at points in Red's half with Red's left princess down (and, as controls,
none down / both down). Prints the engine's DEPLOY_REASONS per point.   python pocket_probe.py   (PARITY_SIM_PATH / ROYALE_RUNTIME)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402

eng = F.Engine(); b = eng.b; sim = eng.sim
K = eng.ids['Knight']
pts = {'own half (9000,8000)': (9000, 8000), 'left pocket (4500,21000)': (4500, 21000), 'left deep (3500,23500)': (3500, 23500),
       'right pocket (13500,21000)': (13500, 21000), 'right deep (14500,23500)': (14500, 23500),
       'centre beyond river (9000,20000)': (9000, 20000), 'left just past river (4500,17500)': (4500, 17500),
       'right just past river (13500,17500)': (13500, 17500)}
for label, red in (('no princess down', [4824, 3052, 3052]), ('Red LEFT down', [4824, 0, 3052]), ('Red RIGHT down', [4824, 3052, 0]),
                   ('both down', [4824, 0, 0])):
    out = []
    for name, (x, y) in pts.items():
        b.reset(1, [[K], [K]], 0, 200, None, [[4824, 3052, 3052], red], [], levels=[[15], [15]], tower_levels=[15, 15])
        before = json.loads(b.save()); after = json.loads(json.dumps(before))
        p = after['players'][0]
        p['mana'] = after['calib']['max_mana'] * after['mana_unit']; p['refill_ms'] = 0
        load_edited(b, before, after)
        st = json.loads(b.state_json())
        hand = st['players'][0]['hand'] if 'players' in st else None
        slot = next((i for i, c in enumerate(json.loads(b.save())['players'][0]['hand']) if c != F.NO_CARD), 0)
        r = b.step([(0, slot, round(x * 18), round(y * 18))], 0)[0]
        out.append(f'{name}: {sim.DEPLOY_REASONS[r[1]]}')
    print(label, '|', '; '.join(out))
