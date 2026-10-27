"""F1c-2 check "fin16 output unchanged": sha256 over RoyaleSim fin16's state_json + sim_unit_state.extract at every 5th tick
of N census scenarios (cue_ab.py's script), RoyaleSim only. Run once per code tree (CB=...) and compare the digests.

usage: CB=/workspace/f1c/cb ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I rs_hash.py N
"""
import hashlib
import json
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB", "/workspace/f1c/cb")]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cue_ab  # noqa: E402
from pipeline import royale_heroiw as heroiw  # noqa: E402
from pipeline.sim_unit_state import extract  # noqa: E402
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
rs = RustEngine(**heroiw.engine_options())
rs.set_command_delay_ticks(20)
ids = {c.name: c.card_id for c in rs.cards()}
kinds = {c.card_id: c.card_kind for c in rs.cards()}
h, samples = hashlib.sha256(), 0
for i, (d0, f0, d1, f1) in enumerate(cue_ab.census()[:n]):
    try:
        rs.reset(1000 + i, MatchSetup(decks=[[ids[x] for x in d0], [ids[x] for x in d1]], shuffle=ShuffleMode.NONE,
                                      forms=[f0, f1], levels=[[16] * 8, [16] * 8], tower_levels=[16, 16]))
    except ValueError:
        continue
    sc, memo = cue_ab.Script(i, kinds), {}
    for tick in range(0, 1200, 5):
        cmds = []
        for side in sc.due(tick):
            k = sc.k[side]
            sc.k[side] += 1
            card = rs.state().players[side].hand[k % 4]
            if card >= 0:
                x, y = sc.place(side, card)
                cmds.append(DeployCommand(side, k % 4, int(x * 18000), int(y * 18000)))
        rs.step(cmds, 5)
        if rs.state().game_over:
            break
        h.update(rs._battle.state_json())
        h.update(json.dumps(extract(rs._battle, memo, hit_window_ms=100), sort_keys=True).encode())
        samples += 1
print(json.dumps({"scenarios": n, "samples": samples, "sha256": h.hexdigest(), "cb": os.environ.get("CB")}))
