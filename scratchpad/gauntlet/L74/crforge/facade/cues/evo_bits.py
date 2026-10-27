"""F1c-2 probe: status bits of evolved bodies in both engines. Blue plays its evolution-slot card (deck slot 0, form 1)
and cycles filler spells so the evolution comes round (RoyaleSim evo_cycle), Red nothing; prints body name, form flag and status_flags
for side-0 troops / buildings every 40 ticks.

usage: ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I evo_bits.py Knight
"""
import json
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB", "/workspace/f1c/cb")]

from pipeline.crforge_core import CrforgeCore  # noqa: E402
from pipeline import royale_heroiw as heroiw  # noqa: E402
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

card = sys.argv[1] if len(sys.argv) > 1 else "Knight"
FILL = ["Zap", "Arrows", "Fireball", "Rocket", "Earthquake", "Freeze", "Poison", "Lightning"]
rs = RustEngine(**heroiw.engine_options())
rs.set_command_delay_ticks(20)
cf = CrforgeCore()
ids = {c.name: c.card_id for c in rs.cards()}
d0 = [card] + FILL[:7]
setup = MatchSetup(decks=[[ids[n] for n in d0], [ids[n] for n in FILL]], shuffle=ShuffleMode.NONE,
                   forms=[[1] + [0] * 7, [0] * 8], levels=[[16] * 8, [16] * 8], tower_levels=[16, 16])
rs.reset(1, setup)
cf.reset(1, setup)
seen = set()
for t in range(0, 2400, 10):
    cmds = []
    hand = rs.state().players[0].hand
    if t % 60 == 0 and t >= 200:              # the card at our side when in hand, else cycle a filler spell
        if ids[card] in hand:
            cmds.append(DeployCommand(0, hand.index(ids[card]), int(3.5 * 18000), int(12.5 * 18000)))
        else:
            cmds.append(DeployCommand(0, 0, int(9 * 18000), int(25.5 * 18000)))
    rs.step(cmds, 10)
    cf.step(cmds, 10)
    for nm, eng in (("rs", rs), ("cf", cf)):
        names = json.loads(eng._battle.unit_types_json())
        for e in eng.state().entities:
            if e.team == 0 and e.kind in (0, 1):
                key = (nm, names[e.unit_type], e.status_flags)
                if key not in seen:
                    seen.add(key)
                    print(t, key, json.dumps([list(v) for v in eng.state().players[0].evo]))
