"""pipeline.crforge_core (F1): the crforge facade behind RoyaleSim's engine-core interface. Skips cleanly without JPype,
the crforge jars / tables (CRFORGE_LIB / CRFORGE_TABLES) or the compiled CfCore (CRFORGE_FACADE_BUILD; javac of
scratchpad/gauntlet/L74/crforge/facade/CfCore.java). Pod 32657: ROYALE_RUNTIME=fin16-linux, PYTHONPATH=/workspace/cfspeed/pylib.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

import pytest

jpype = pytest.importorskip("jpype")
LIB = Path(os.environ.get("CRFORGE_LIB", "/workspace/cfspeed/crforge/env/build/install/env/lib"))
TABLES = Path(os.environ.get("CRFORGE_TABLES", "/workspace/cfspeed/crforge_cache/tables/16.402.22"))
BUILD = Path(os.environ.get("CRFORGE_FACADE_BUILD", "/workspace/f1/build"))
if not (any(LIB.glob("core-*.jar")) and (TABLES / "spells_other.json").is_file() and (BUILD / "CfCore.class").is_file()):
    pytest.skip("crforge jars / tables / compiled CfCore absent", allow_module_level=True)
try:
    from pipeline import crforge_core as C
    from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode
except Exception as exc:                                   # no pinned RoyaleSim runtime here (the catalogue source)
    pytest.skip(f"RoyaleSim runtime not available: {exc!r}", allow_module_level=True)

ICE = ["Knight", "IceWizard", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"]
OPP = ["Witch", "Golem", "Tombstone", "DarkWitch", "GoblinGiant", "FirespiritHut", "GoblinBarrel", "Graveyard"]


def _setup(core):
    return MatchSetup(decks=[[core.ids[n] for n in ICE], [core.ids[n] for n in OPP]], shuffle=ShuffleMode.NONE,
                      forms=[[1, 2, 1, 0, 0, 0, 0, 0], [0] * 8])


def _play(core, rng, ticks):
    for _ in range(ticks // 10):
        cmds = [DeployCommand(s, rng.randrange(4), 18 * rng.randrange(500, 17500), 18 * rng.randrange(500, 31500))
                for s in (0, 1) if rng.random() < 0.3]
        core.step(cmds, 10)


def test_spell_objects_follow_the_tables():
    m = C.spell_objects(TABLES)
    assert m["RocketSpell"] == ("Rocket", 0) and m["LogProjectile"] == ("Log", 0)
    assert m["LogProjectileRolling"] == ("Log", 2)        # spawned by the first projectile: the roll
    assert m["Tornado"][0] == "Tornado" and m["Tornado"][1] in (3, 4)


def test_reset_deals_in_order_in_royalesim_units():
    core = C.CrforgeCore()
    core.reset(5, _setup(core))
    st = core.state()
    assert st.players[0].hand == [core.ids[n] for n in ICE[:4]] and st.players[0].next_card == core.ids[ICE[4]]
    kings = {e.team: (e.x, e.y) for e in st.entities if e.kind == 2}
    assert kings == {0: (162000, 54000), 1: (162000, 522000)}  # RoyaleSim's measured king centres (royale_env SCALE note)
    assert st.players[0].elixir_milli > 0 and not st.game_over


def test_save_load_is_identical_and_forks_are_independent():
    core = C.CrforgeCore()
    core.reset(11, _setup(core))
    _play(core, random.Random(1), 900)
    blob = core.save_state()
    ref = []
    for k in range(3):                                    # three forks, fresh cores, the same script
        f = C.CrforgeCore()
        f.load_state(blob)
        _play(f, random.Random(2), 600)
        ref.append(f._battle.state_json())
    assert ref[0] == ref[1] == ref[2]
    _play(core, random.Random(2), 600)                    # the uninterrupted run
    assert core._battle.state_json() == ref[0]
    other = C.CrforgeCore()
    other.load_state(blob)
    _play(other, random.Random(3), 600)
    assert other._battle.state_json() != ref[0]


def test_royale_env_runs_on_the_facade():
    from pipeline import obs_contract as oc
    from pipeline.royale_env import RoyaleSelfPlayEnv
    env = RoyaleSelfPlayEnv(forms_mode="deck", feature_version=6)
    env.core = C.CrforgeCore()
    env.reset(ICE, OPP, seed=3)
    for t in range(100, 1200, 30):
        for side in (0, 1):
            for i in range(8):
                if env.act(side, i, 9000, 10000 if side == 0 else 22000)["accepted"]:
                    break
        env.advance_to(t)
    raw = env.raw()
    names = {e["name"] for e in raw["entities"]}
    assert names and names <= set(env.ids)
    bs = oc.from_engine(raw, 0, oc.load_deck("icebow"), feature_version=6, unmapped=set())
    tok, mask, sc = oc.to_tokens(bs)
    assert mask.sum() > 0 and env.public_plays
