"""F1c-2 probe: the crforge facade's cue projectiles (extract) next to cueSave's raw shot rows, Red Firecracker vs Blue
Knight (trace.py's placements). Prints the first ticks that hold a shot."""
import json
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB", "/workspace/f1c/cb")]

from pipeline.crforge_core import CrforgeCore  # noqa: E402
from pipeline.sim_unit_state import extract  # noqa: E402
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402

FILL = ["Zap", "Arrows", "Fireball", "Rocket", "Earthquake", "Freeze", "Poison", "Lightning"]
red = sys.argv[1] if len(sys.argv) > 1 else "Firecracker"
cf = CrforgeCore()
d0, d1 = ["Knight"] + FILL[:7], [red] + FILL[:7]
cf.reset(1, MatchSetup(decks=[[cf.ids[n] for n in d0], [cf.ids[n] for n in d1]], shuffle=ShuffleMode.NONE,
                       forms=[[0] * 8, [0] * 8]))
shown = 0
for t in range(500):
    cmds = []
    if t == 140:
        cmds.append(DeployCommand(0, 0, int(3.5 * 18000), int(10.5 * 18000)))
    if t == 180:
        cmds.append(DeployCommand(1, 0, int(3.5 * 18000), int(18.5 * 18000)))
    cf.step(cmds, 1)
    c = extract(cf._battle, {})
    if c["projectiles"] and shown < 4:
        shown += 1
        sv = json.loads(cf._battle.save())
        st = json.loads(cf._battle.state_json())
        print(t, "extract", c["projectiles"])
        print("   save", sv["projectiles"], "\n   state", st["projectiles"])
        print("   units", [(u["uid"], u["name"]) for u in c["units"] if u["kind"] == "troop"])
