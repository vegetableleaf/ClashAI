"""F1c-2 (from F1c-1b mm_trace.py): the Mighty Miner bomb tick by tick, new side-0 bodies and side-0 spell
rows, first seed only.
F1c-1b: Mighty Miner's lane switch, tick by tick after a press, on RoyaleSim fin16 with the engine's own 20-tick
command delay (as crforge runs every command) and on the crforge facade, from the same scripted start: the miner's
position / status flags / buffs, side-0 bodies new since the press (unit type), side-0 spell rows. Seeds 1..N.
usage: [ROYALE_ENGINE=crforge] ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I mm_trace.py --n 3
"""
import argparse
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB_TREE", "/workspace/f1/rl")]
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from royalegym.protocol import HAND_SIZE, DeployCommand  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--opp", default="none", help="none: no enemy near; knight: a Knight walks at the miner")
a = ap.parse_args()
DECK = ["MightyMiner", "Knight", "Log", "Skeletons", "Tesla", "Rocket", "Tornado", "Xbow"]
OPP = ["Knight", "Valkyrie", "Musketeer", "Log", "HogRider", "Fireball", "Skeletons", "Cannon"]
out = []
for seed in range(1, a.n + 1):
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6, hero_abilities=True,
                            ability_policy="v2")
    env.core.set_command_delay_ticks(20)
    env.reset(DECK, OPP, seed=seed)
    mm = env.ids["MightyMiner"]
    while env.tick < 1500:                        # cycle the hand until the miner can be played, then play it
        st = env.core.state()
        if mm in st.players[0].hand and st.players[0].elixir_milli >= 4000 and env.act(
                0, env.deck_ids[0].index(mm), 9000, 8000)["accepted"]:
            if a.opp == "knight":
                env.act(1, env.deck_ids[1].index(env.ids["Knight"]), 9000, 18000)
            break
        if st.players[0].elixir_milli >= 7000:
            for c in st.players[0].hand:
                if c != mm and env.act(0, env.deck_ids[0].index(c), 3000, 2000)["accepted"]:
                    break
        env.advance_to(env.tick + 5)
    press = None
    for _ in range(300):
        env.advance_to(env.tick + 1)
        if env.core.check_deploy(DeployCommand(0, HAND_SIZE, 0, 0)) == 0:
            press = DeployCommand(0, HAND_SIZE, 0, 0)
            break
    if press is None:
        out.append(dict(seed=seed, error="never ready"))
        continue
    st0 = env.core.state()
    before = {e.uid for e in st0.entities}
    hero = max((e for e in st0.entities if e.team == 0 and e.card_id == mm), key=lambda e: e.max_hp)
    t0 = env.tick
    (r,) = env.core.step([press], 0)
    for k in range(1, 60):
        env.advance_to(t0 + k)
        st = env.core.state()
        types = env.core.unit_types()
        if k in (49, 50) and os.environ.get("ROYALE_ENGINE") == "crforge":
            import jpype
            print(k, "areas", jpype.JClass("CueTrace").areas(env.core._cf), flush=True)
        if 26 <= k <= 56:
            print(k, "ents", [(types[x.unit_type], x.kind, x.card_id, x.x // 18, x.y // 18, x.hp, x.deploy_ticks)
                              for x in st.entities if x.uid not in before and x.team == 0],
                  "spells", [{k: v for k, v in __import__("msgspec").structs.asdict(sp).items() if k not in ("team",)} for sp in st.spells if sp.team == 0], flush=True)
    break
