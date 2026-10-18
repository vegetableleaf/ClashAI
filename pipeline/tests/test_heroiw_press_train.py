"""L74 overpress (10-18): training can use the LIVE Hero IW press rule (rl_royale ``heroiw_press``), never silently the
generic one under an ability head, and the evaluation can decode the head as trained (search_s0 --ability-head-decode).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_heroiw_press_train.py
"""
from __future__ import annotations

import pytest

from pipeline import rl_royale as RL
from pipeline import royale_heroiw as H

RE = pytest.importorskip("pipeline.royale_env")   # activates the pinned runtime BEFORE a test fakes H.ENABLED

BASE = dict(seed=74, hero_abilities=True, ability_policy="v2", advantage="gae")


@pytest.fixture
def env(monkeypatch):
    for k in ("ROYALE_HEROIW_PRESS", "ROYALE_HEROIW_FORM"):   # setenv first: teardown restores the ORIGINAL (heroiw_press_cfg
        monkeypatch.setenv(k, "x")                         # writes os.environ directly)
        monkeypatch.delenv(k)
    monkeypatch.setattr(H, "ENABLED", True)
    return monkeypatch


def test_hash_unchanged_when_absent_or_null():
    assert RL.config_sha(BASE) == RL.config_sha({**BASE, "heroiw_press": None})
    assert RL.config_sha({**BASE, "heroiw_press": "live"}) != RL.config_sha(BASE)


def test_key_sets_the_env_and_refuses_a_conflict(env):
    import os
    assert RL.heroiw_press_cfg({**BASE, "heroiw_press": "live"}) == "live"
    assert os.environ["ROYALE_HEROIW_PRESS"] == "live"
    assert RL.heroiw_press_cfg({**BASE, "heroiw_press": "live"}) == "live"      # same value again (smoke's 2nd Learner)
    with pytest.raises(SystemExit, match="environment has"):
        RL.heroiw_press_cfg({**BASE, "heroiw_press": "never"})
    with pytest.raises(SystemExit, match="must be one of"):
        RL.heroiw_press_cfg({**BASE, "heroiw_press": "on"})


def test_absent_key_leaves_the_env_alone(env):
    import os
    assert RL.heroiw_press_cfg(BASE) == "off" and "ROYALE_HEROIW_PRESS" not in os.environ
    env.setenv("ROYALE_HEROIW_PRESS", "live")                                    # the old way (env only) still works
    assert RL.heroiw_press_cfg({**BASE, "ability_head": True}) == "live"


def test_ability_head_refuses_the_generic_iw_teacher(env):
    ab = {**BASE, "ability_head": True}
    for mode in (None, "off", "never"):
        cfg = ab if mode is None else {**ab, "heroiw_press": mode}
        env.delenv("ROYALE_HEROIW_PRESS", raising=False)
        with pytest.raises(SystemExit, match="REFUSING: ability_head"):
            RL.heroiw_press_cfg(cfg)
    env.delenv("ROYALE_HEROIW_PRESS", raising=False)
    assert RL.heroiw_press_cfg({**ab, "heroiw_press": "live"}) == "live"
    env.delenv("ROYALE_HEROIW_PRESS", raising=False)
    assert RL.heroiw_press_cfg(BASE) == "off"                                     # no head: the rule press, allowed
    assert RL.heroiw_press_cfg({**ab, "hero_abilities": False}) == "off"         # no button is ever pressable
    env.setenv("ROYALE_HEROIW_FORM", "normal")                                    # no Hero IW in the deck
    assert RL.heroiw_press_cfg(ab) == "off"
    env.setattr(H, "ENABLED", False)                                              # a runtime without Hero IW
    env.delenv("ROYALE_HEROIW_FORM")
    assert RL.heroiw_press_cfg(ab) == "off"


def test_loadability_env_ignores_the_live_rule(env):
    RoyalePoolEnv = RE.RoyalePoolEnv
    env.setattr(H, "engine_options", lambda: {})   # laptop runtime: no Hero IW card table (ENABLED is faked here)
    env.setenv("ROYALE_HEROIW_PRESS", "live")
    with pytest.raises(ValueError, match="Live IW press rule"):                 # the guard itself is unchanged
        RoyalePoolEnv(decision_ticks=10)
    e = RoyalePoolEnv(decision_ticks=10, iw_press="off")                         # Learner._entries' env
    assert getattr(e, "_iw_policy", None) is None and not e._iw_never
    with pytest.raises(ValueError, match="iw_press must be"):
        RoyalePoolEnv(decision_ticks=10, iw_press="live")


def test_search_s0_decode_flag(monkeypatch, tmp_path):
    """--ability-head-decode: absent = greedy; sample reaches the learner's ability cfg."""
    import torch
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
    from pipeline.tests.test_search_s0 import tiny_models
    gen = tiny_models()[0]
    ck = tmp_path / "ck.pt"
    torch.save({"rl": {"ability_head": RL.AbilityHead(16).state_dict(),
                       "ability": {"d_g": 16, "hidden": 64, "n_feat": E.ABILITY_FEAT_N, "bc": None}}}, ck)
    monkeypatch.setattr(E, "load_policy", lambda path, dev: (gen, {"grid": "lattice"}))
    monkeypatch.setattr(RL, "load_posture_head", lambda path, dev: None)
    args = {"gen": str(ck), "opps": [], "threads": 1, "tail_cap": 600, "horizon": 12.0, "interval": 1, "topk": 4,
            "cells": 3, "device": "cpu", "search_min_p": 0.0, "hero_abilities": True}
    S._init_worker(args)
    assert S._W["runner"].lcfg["ability"]["mode"] == "greedy"
    S._init_worker({**args, "ability_head_decode": "sample"})
    assert S._W["runner"].lcfg["ability"]["mode"] == "sample"


# ---- ability_features 'freeze' (L74 press audit 10-18) -----------------------------------------------------------
AB = {**BASE, "ability_head": True}


def test_features_hash_and_validation():
    assert RL.config_sha(AB) == RL.config_sha({**AB, "ability_features": None}) == RL.config_sha({**AB, "ability_features": "base"})
    assert RL.config_sha({**AB, "ability_features": "freeze"}) != RL.config_sha(AB)
    assert RL.ability_cfg({**AB, "ability_features": "freeze"})["features"] == "freeze"
    assert RL.ability_cfg(AB)["features"] == "base"
    with pytest.raises(SystemExit, match="without ability_head"):
        RL.ability_cfg({**BASE, "ability_features": "freeze"})
    with pytest.raises(SystemExit, match="ability_features must be"):
        RL.ability_cfg({**AB, "ability_features": "cube"})
    c = dict(AB)
    RL.store_ability_cfg(c)
    assert "ability_features" not in c                      # base stays absent: old configs / hashes unchanged
    c = {**AB, "ability_features": "freeze"}
    RL.store_ability_cfg(c)
    assert c["ability_features"] == "freeze"


def test_feature_counts_agree():
    from pipeline import e1_eval as E
    assert E.ABILITY_FEAT_SETS == {"base": RE.ABILITY_FEAT_N, "freeze": RE.ABILITY_FEAT_N + RE.FREEZE_FEAT_N}
    assert RL.AbilityHead(8, n_feat=E.ABILITY_FEAT_SETS["freeze"]).net[0].in_features == 8 + 55


def _ent(uid, team, x, y, card=1, kind=None, buffs=(), hp=100, target=-1):
    from types import SimpleNamespace as NS
    return NS(uid=uid, team=team, x=x * 18000, y=y * 18000, card_id=card, hp=hp, kind=RE.EntityKind.TROOP if kind is None
              else kind, buffs=buffs, target_uid=target)


def test_freeze_features_geometry():
    """Side 0 (my half y < 16): IW at (9, 12); a marked HogRider at (9, 17) with a Skeleton beside it -> target = the
    marked troop, cube at y 18.5; an unmarked closer troop is NOT the target; a building near is not a troop."""
    from types import SimpleNamespace as NS
    names = {1: "Skeletons", 2: "HogRider", 3: "IceWizard", 4: "Cannon"}
    env = NS(names=names, _body_elixir={1: 0.33, 2: 4.0, 4: 3.0}, _card_cost={1: 1.0, 3: 3.0},
             _ability_cost=lambda side, cid, row: 2)
    hero = _ent(10, 0, 9, 12, card=3, target=12)
    ents = [hero, _ent(11, 1, 9, 17, card=2, buffs=(("IceWizardHeroSlow", 900),)),
            _ent(12, 1, 9.5, 13, card=1),                                   # closer, unmarked: not the target
            _ent(13, 1, 10, 18.5, card=1),                                  # 1.1 t from the cube point
            _ent(14, 1, 9, 19, card=4, kind=RE.EntityKind.BUILDING)]        # a building: never counted
    st = NS(entities=ents, players=[NS(hand=[1, 3, RE.EMPTY_CARD, 1], elixir_milli=7000, abilities=[None])])
    f = RE.RoyalePoolEnv._freeze_features(env, 0, 0, 3, hero, st)
    assert len(f) == RE.FREEZE_FEAT_N
    # target (9, 17): HogRider itself + Skeleton (10, 18.5) at 1.80 t -> 2 troops, 4.33 elixir, wincon
    assert f[:4] == [1., 2 / 5, pytest.approx(4.33 / 10), 1.]
    # cube (9, 18.5): HogRider 1.5 t, Skeleton 1.0 t -> 2 troops
    assert f[4:7] == [2 / 5, pytest.approx(4.33 / 10), 1.]
    assert f[7] == pytest.approx((18.5 - 6.5) / 10) and f[8] == 0.     # cube on the enemy half
    assert f[9] == 1. and f[10] == pytest.approx((7 - 2 - 1) / 10)
    for e in ents[1:]:                                                  # nobody marked -> the IW's attack target (uid 12)
        e.buffs = ()
    g = RE.RoyalePoolEnv._freeze_features(env, 0, 0, 3, hero, st)
    assert g[0] == 1. and g[9] == 0. and g[1] == 1 / 5                  # (9.5, 13): only itself within 2.5 t
    hero.target_uid = -1
    assert RE.RoyalePoolEnv._freeze_features(env, 0, 0, 3, hero, st)[:9] == [0.] * 9
    assert RE.RoyalePoolEnv._freeze_features(env, 0, 0, 1, hero, st) == [0.] * RE.FREEZE_FEAT_N   # not the IW
