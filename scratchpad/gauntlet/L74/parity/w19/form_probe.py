"""The fork's Skeletons formation (Battle.formation_preview) at the taps of the L16-era lane-flip fights vs the live layout.
  python form_probe.py   (PARITY_SIM_PATH)"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
eng = F.Engine(); b = eng.b
b.reset(1, [[eng.ids['Skeletons']], [eng.ids['Skeletons']]], 0, 200, None, [[4824, 3052, 3052], [4824, 3052, 3052]], [], levels=[[16], [16]], tower_levels=[16, 16])
for team in (0, 1):
    for x, y in ((8500, 500), (8500, 533), (8500, 10500), (9500, 10500), (8000, 10500), (8500, 12500), (3500, 10500), (14500, 10500)):
        try:
            pts = b.formation_preview(team, 'Skeletons', x * 18, y * 18)
        except Exception as e:  # noqa: BLE001
            pts = str(e)
        print(team, (x, y), [(n, round(px / 18), round(py / 18), d) for n, px, py, d in pts] if isinstance(pts, list) else pts)
