"""W8 probe: the SIM's regen steps around the 2x / 3x switches after a scenario reset (the J4 harness's reset), in 1/10000.
  PARITY_SIM_PATH=... python probe_2x.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402

eng = F.Engine(); b = eng.b
for start, lo, hi in ((60, 60, 80), (2300, 2392, 2412), (4700, 4792, 4812)):
    b.reset(1, [[eng.ids['Knight']], [eng.ids['Knight']]], 0, start, [0, 0], None, [], levels=[[16], [16]], tower_levels=[16, 16])
    unit = json.loads(b.save())['mana_unit']
    st = json.loads(b.state_json()); print('reset at', start, 'state tick', st['tick'], 'unit', unit, 'rate', st.get('elixir_rate'))
    prev = None
    while True:
        s = json.loads(b.save()); t = json.loads(b.state_json())['tick']; m = s['players'][0]['mana']
        if prev is not None and lo <= t <= hi:
            print('  into t', t, 'step', (m - prev) * 10000 / unit)
        if t >= hi:
            break
        # keep the bar empty so the cap never stops the regen
        if m > 5 * unit:
            after = json.loads(json.dumps(s)); after['players'][0]['mana'] = 0; load_edited(b, s, after); m = 0
        prev = m
        b.step([], 1)
