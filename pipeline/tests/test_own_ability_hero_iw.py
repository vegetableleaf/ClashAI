"""L74 econ2 parity fix, live-only switch --hero-ability-spec {off, supplement}.
off (default) = the pinned catalog: my Hero Ice Wizard reads 'readiness unknown', identical to main.
supplement    = a live frame with my Hero IW yields the TRAINING-style own-ability token (ready_known 1, charges /
                cooldown from my own deploy + press history and the catalog).
Run: icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_own_ability_hero_iw.py"""
import argparse
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from pipeline.own_ability import ABILITY_COLS, HERO_SPECS, catalog, observe, tokens

REPO = Path(__file__).resolve().parents[2]
PRE_FIX = "58afe72123c62fa11cf32a68457049edec7a9bc1"     # main HEAD when the switch was added
GID = {"ice-wizard": 62}
ME = 0
C = {k: i for i, k in enumerate(ABILITY_COLS)}
DEPLOY = [dict(card="ice-wizard", tick=100, side=ME, accepted=True, ability=False)]
PRESS = DEPLOY + [dict(card="IceWizard", tick=200, side=ME, accepted=True, ability=True)]   # live record_ability name


def frame(tick, hero=True):
    ents = [dict(side=ME, x=9000, y=8000, card_id=203000023, hp=700, max_hp=700, kind=15, address="0xa")] if hero else []
    ents.append(dict(side=1, x=9000, y=24000, card_id=26000000, hp=1400, max_hp=1400, kind=15, address="0xb"))
    return dict(game_tick=tick, entities=ents, projectiles=[], effects=[], players=[])


def row(tick, events, hero=True, spec="supplement"):
    return tokens(observe(frame(tick, hero), ME, "reader"), GID, events, tick, hero_spec=spec)[0]


def main_module():
    """pipeline/own_ability.py as on main before the fix (PRE_FIX, pinned so the check survives the merge)."""
    try:
        src = subprocess.check_output(["git", "show", f"{PRE_FIX}:pipeline/own_ability.py"], cwd=REPO, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git main not available")
    mod = types.ModuleType("pipeline._own_ability_main"); mod.__package__ = "pipeline"
    mod.__file__ = str(REPO / "pipeline/own_ability.py"); sys.modules[mod.__name__] = mod
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return mod


def test_catalog_switch():
    assert HERO_SPECS == ("off", "supplement")
    assert ("ice-wizard", 2) not in catalog() and ("ice-wizard", 2) not in catalog("off")
    spec = catalog("supplement")[("ice-wizard", 2)]
    assert spec["max_charges"] == 1 and spec["deploy_ms"] == 1000 and not spec.get("cooldown_ms")
    assert set(catalog("supplement")) - set(catalog("off")) == {("ice-wizard", 2)}
    with pytest.raises(ValueError):
        catalog("on")


def test_flag_off_identical_to_main_on_a_hero_frame():
    M = main_module()
    for t, ev in ((110, DEPLOY), (150, DEPLOY), (210, PRESS), (150, [])):
        rows = observe(frame(t), ME, "reader")
        assert np.array_equal(tokens(rows, GID, ev, t), M.tokens(M.observe(frame(t), ME, "reader"), GID, ev, t))
        assert np.array_equal(tokens(rows, GID, ev, t, hero_spec="off"), tokens(rows, GID, ev, t))
    r = row(150, DEPLOY, spec="off")
    assert r[C["ready_known"]] == 0 and r[C["remaining_charges"]] == -1 and r[C["cooldown_s"]] == -1   # today's live token


def test_flag_on_gives_training_style_token():
    assert observe(frame(100), ME, "reader") == [("ice-wizard", 2, 1, -1.0, 0.0)]
    r = row(110, DEPLOY)                                   # deploying: not ready yet, 0.5 s to go (a training value)
    assert r[C["ready_known"]] == 1 and r[C["ready"]] == 0 and r[C["remaining_charges"]] == 1 and abs(r[C["cooldown_s"]] - .5) < 1e-6
    assert list(row(150, DEPLOY)) == [62, 2, 1, 1, 1, 1, 0]          # ready, one charge
    assert list(row(210, PRESS)) == [62, 2, 1, 0, 1, 0, 0]           # the one charge is spent
    r = row(150, [])
    assert r[C["ready_known"]] == 0 and r[C["remaining_charges"]] == -1  # no own deploy seen: stays explicitly unknown


def test_no_hero_frame_unchanged_either_way():
    for spec in HERO_SPECS:
        assert not np.any(tokens(observe(frame(150, hero=False), ME, "reader"), GID, DEPLOY, 150, hero_spec=spec))


def test_public_observer_rows_with_the_pilot_override():
    """The live pilot's path: PublicObserver (reader frames + own_events) -> rows; GenPilot.row re-tokenises them with
    hero_spec when the switch is on (live_gen.py), features() itself stays 'off'."""
    from bisect import bisect_right
    from pipeline.public_observation import PublicObserver
    obs = PublicObserver(ME)
    for t in (90, 100, 150):
        obs.update(frame(t), source="reader")
    obs.own_events.append(dict(card="ice-wizard", tick=95, side=ME, accepted=True, ability=False))
    off = obs.features(150, GID)["own_ability"]
    assert off[0][C["ready_known"]] == 0
    ai = bisect_right(obs.ability_ticks, 150) - 1
    on = tokens(obs.ability_rows[ai], GID, obs.own_events, 150, hero_spec="supplement")
    assert list(on[0]) == [62, 2, 1, 1, 1, 1, 0] and not np.any(on[1:])


LIVE_CKPT = REPO / "icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt"


def test_gen_pilot_switch_changes_only_the_hero_ability_token():
    """GenPilot.row (the live model input) on reader frames with MY Hero Ice Wizard: off = today's 'unknown' token;
    supplement = the training-style token; every other input byte-identical; no hero on board = identical rows."""
    import copy
    import torch
    from pipeline.live_gen import GenPilot
    from pipeline.tests.test_live_mem import FRAME, T
    if not LIVE_CKPT.is_file():
        pytest.skip("live checkpoint not available")
    torch.set_num_threads(1)
    off, on = GenPilot(LIVE_CKPT), GenPilot(LIVE_CKPT, hero_ability_spec="supplement")
    with pytest.raises(ValueError):
        GenPilot(LIVE_CKPT, hero_ability_spec="on")
    iw = off.gid["ice-wizard"]
    rows = {}
    for tick, hero in ((206, False), (230, True), (260, True)):
        f = copy.deepcopy(FRAME); f["game_tick"] = tick
        if hero:                                         # side 1 = me in FRAME
            f["entities"].append(T(5000009, 15, 1, 9000, 26000, 700, 700, cid=203000023, addr="0x7a5877aa0000"))
        for p in (off, on):
            p.observe(f)
            if tick == 230:
                p.record_play(iw, 2, (.5, .8), 229 * .05)  # my Hero IW confirmed at tick 229
        rows[tick] = [p.row(f)[0] for p in (off, on)]
    for tick, (x, y) in rows.items():
        for k in x:
            if k != "own_ability" or tick == 206:
                assert torch.equal(x[k], y[k]), (tick, k)
    x, y = (r["own_ability"][0, 0].tolist() for r in rows[260])
    assert x[:2] == [iw, 2] and x[C["ready_known"]] == 0 and x[C["cooldown_s"]] == -1      # off: unknown, as today
    assert y == [iw, 2, x[C["living_controllers"]], 1, 1, 1, 0]                           # on: ready, 1 charge


def test_live_options_file_accepts_the_switch(tmp_path):
    from pipeline.decision_options import add_arguments
    from pipeline.live_options import add_live_options_arguments, parse_with_live_options
    f = tmp_path / "LIVE_OPTIONS"; f.write_text("--spell-aim rocket_area --hero-ability-spec supplement\n")
    ap = argparse.ArgumentParser(); add_arguments(ap)
    ap.add_argument("--hero-ability-spec", choices=HERO_SPECS, default="off"); add_live_options_arguments(ap, f)
    a, rec = parse_with_live_options(ap, [])
    assert a.hero_ability_spec == "supplement" and rec["from_file"]["hero_ability_spec"] == "supplement"
    a, rec = parse_with_live_options(ap, ["--hero-ability-spec", "off"])          # explicit flag wins
    assert a.hero_ability_spec == "off" and "hero_ability_spec" in rec["explicit"]
    f.write_text("--spell-aim rocket_area\n")
    a, rec = parse_with_live_options(ap, [])                                      # absent from the file: default off
    assert a.hero_ability_spec == "off" and "hero_ability_spec" not in rec["from_file"]
