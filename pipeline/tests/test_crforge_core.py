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


def _press_hero(deck, card, cost):
    """F1c-1: RoyaleSim fin16's ability format (abil_probe.py / abil_repress.py on pod 32657): a row per button from the
    deal on, STATUS_HERO on the hero body only, the press refused (CARD_PENDING) while it waits, spent at its run.
    ``card`` sits at hand slot 0 of ``deck`` in its hero form."""
    from royalegym.protocol import DeployStatus as S
    core = C.CrforgeCore()
    core.reset(7, MatchSetup(decks=[[core.ids[n] for n in deck], [core.ids[n] for n in OPP]], shuffle=ShuffleMode.NONE,
                             forms=[[2] + [0] * 7, [0] * 8]))
    cid = core.ids[card]
    st = core.state()
    assert [r[:4] for r in st.players[0].abilities] == [[0, 0, cost, cid]] and st.players[1].abilities == []
    press = DeployCommand(0, 4, 0, 0)
    assert core.check_deploy(press) == S.NO_HERO
    core.step([], 90)                                     # past the start cooldown (TOO_EARLY)
    (r,) = core.step([DeployCommand(0, 0, 18 * 9000, 18 * 8000)], 1)
    assert r.status == S.OK
    for _ in range(400):
        if core.check_deploy(press) == S.OK:
            break
        core.step([], 1)
    st = core.state()
    hero = [e for e in st.entities if e.team == 0 and e.card_id == cid and e.status_flags & 16]
    assert len(hero) == 1 and core.check_deploy(press) == S.OK      # the body, not its summons (the IW's cube)
    assert (hero[0].uid, card + "_hero") in core._battle.debug_units()
    e0 = st.players[0].elixir_milli
    (r,) = core.step([press], 1)
    assert r.status == S.OK
    # F635b: the waiting press's cost is promised (set aside by every play given before its run), also for a hero no
    # play made (by object id), on a crforge build with the fork's by-id giving (CfCore.promisesById); not on the pin.
    by_id = card == "BarbLog"
    assert core._cf.promised(0) == (cost if not by_id or core._cf.promisesById() else 0)
    for _ in range(20):                                   # given at t0, runs at t0 + 20
        assert core.check_deploy(press) == S.CARD_PENDING and core.state().players[0].abilities[0][:2] == [1, 0]
        core.step([], 1)
    st = core.state()                                     # t0 + 21: the run is visible
    assert st.players[0].abilities[0][:2] == [0, 1] and st.players[0].elixir_milli < e0
    assert core.check_deploy(press) == S.ABILITY_SPENT


def test_hero_ice_wizard_press_runs_20_ticks_later():
    _press_hero(["IceWizard", "Knight", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"], "IceWizard", 2)


def test_hero_barbarian_barrel_press():
    """F1c-1b: the barbarian the hero Barbarian Barrel's log spawns (no play made it: crforge's PlayerCommands cannot
    name it; pressed by object id)."""
    _press_hero(["BarbLog", "Knight", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"], "BarbLog", 1)


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
