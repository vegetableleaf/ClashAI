"""F1c-1: a second press of the same button while the first waits its 20 ticks. RoyaleSim fin16 with the engine's own
command delay set to 20 (set_command_delay_ticks, as crforge runs every command) vs the crforge facade: per census
match, the hero Ice Wizard is played, the first ready tick its button is pressed, then every tick for 25 ticks the
engine's check_deploy of the same button, the row and the side's pending list are recorded; at k = 10 a second press is
given and its result (and whether it spent elixir at its run) recorded.
usage: [ROYALE_ENGINE=crforge] ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I abil_repress.py --n 10
"""
import argparse
import json
import os
import sys
from collections import Counter

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB_TREE", "/workspace/f1/rl")]
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from royalegym.protocol import HAND_SIZE, DeployCommand  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=10)
a = ap.parse_args()
DECK = ["Knight@evolution", "IceWizard@hero", "Tesla@evolution", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"]
OPP = ["Knight", "Valkyrie", "Musketeer", "Log", "HogRider", "Fireball", "Skeletons", "Cannon"]
tot, rows = Counter(), []
for i in range(a.n):
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6, hero_abilities=True,
                            ability_policy="v2")
    env.core.set_command_delay_ticks(20)
    env.reset(DECK, OPP, seed=i)
    iw = env.ids["IceWizard"]
    while env.tick < 600 and not env.done:      # play the IW when in hand and affordable, the opponent a Knight on it
        st = env.core.state()
        if iw in st.players[0].hand and st.players[0].elixir_milli >= 3000 and not any(
                e.card_id == iw and e.team == 0 for e in st.entities):
            env.act(0, env.deck_ids[0].index(iw), 9000, 9000 + 300 * i)
            env.act(1, env.deck_ids[1].index(env.ids["Knight"]), 9000, 18000)
        st = env.core.state()
        if st.players[0].elixir_milli >= 2500 and env.ability_options(0):
            break
        env.advance_to(env.tick + 1)
    opts = env.ability_options(0)
    if not opts:
        tot["no_ready"] += 1
        continue
    button = opts[0]["cmd"][0]
    cmd = DeployCommand(0, HAND_SIZE + button, 0, 0)
    t0 = env.tick
    (r,) = env.core.step([cmd], 0)
    tot[f"first_{int(r.status)}"] += 1
    trace = []
    for k in range(1, 26):
        env.advance_to(t0 + k)
        st = env.core.state()
        chk = int(env.core.check_deploy(cmd))
        tot[f"check_k{'le20' if k <= 20 else 'gt20'}_{chk}"] += 1
        if k == 10:
            (r2,) = env.core.step([cmd], 0)
            tot[f"second_{int(r2.status)}"] += 1
        trace.append([k, chk, st.players[0].abilities, st.players[0].pending, st.players[0].elixir_milli])
    rows.append(dict(i=i, t0=t0, trace=trace))
print(json.dumps(dict(engine=os.environ.get("ROYALE_ENGINE", "royalesim"), totals=dict(tot), first=rows[:1])))
