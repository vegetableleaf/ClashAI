"""Live cue path (step c, STEP_C_SPEC.md section 6): pipeline/live_unit_state.py + GenPilot.row's b["cue"].

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_live_cues.py

Covers: the token match is e1_eval.sim_cue_rows' (same rows on random boards, both sides); each live rule on a synthetic
merged-reader frame; degraded / block-less frames give all-zero rows; the buff memo resets; a model without a cue layer
never reads the cues (rows identical with the builder attached); a cue-layer model refuses without a cue source.
The rule / table tests need the card table (icebow/data/cue_table, or an imported royalesim 0.1.35): skipped without.
"""
import copy
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import sim_unit_state as SU
from pipeline.decision_options import DecisionOptions
from pipeline.live_unit_state import LiveCues, align, load_table
from pipeline.model_gen import CUE_N, CUE_STATES, cue_vector
from pipeline.obs_contract import F as TOK_F
from pipeline.tests.test_live_decision_options import icebow_frame, pilot


@pytest.fixture(scope="module")
def table():
    try:
        return load_table()
    except (FileNotFoundError, ValueError) as exc:
        pytest.skip(f"cue table unavailable: {exc}")


def _unit(rng, uid, team, kind="troop"):
    st = CUE_STATES[rng.integers(len(CUE_STATES))]
    return dict(uid=uid, team=team, kind=kind, x=float(rng.uniform(0, 18)), y=float(rng.uniform(0, 32)), state=st,
                charging=bool(rng.integers(2)), hide=("hidden", "up", None)[rng.integers(3)],
                attack=dict(target=int(rng.integers(0, 4)) if rng.integers(2) else None,
                            phase=("idle", "windup", "hit")[rng.integers(3)], frac=float(rng.random())),
                status=dict(frozen=bool(rng.integers(2)), slowed=bool(rng.integers(2)), raged=False, invisible=False,
                            shielded=bool(rng.integers(2)), slow_frac=float(rng.random()) if rng.integers(2) else None))


@pytest.mark.parametrize("seed", range(40))
def test_align_is_sim_cue_rows(monkeypatch, seed):
    rng = np.random.default_rng(seed)
    side = seed % 2
    tok, mask = np.zeros((64, TOK_F), np.float32), np.zeros(64, bool)
    for i in range(int(rng.integers(0, 14))):
        mask[i] = True
        tok[i, 1 + int(rng.integers(2))] = 1.0                 # mine / enemy
        tok[i, 13] = float(rng.random() < .15)                 # a spell token: never takes a body
        tok[i, 4:6] = rng.random(2)
    units = [_unit(rng, u, int(rng.integers(2))) for u in range(4, 4 + int(rng.integers(0, 14)))]
    units += [dict(_unit(rng, u, u % 2), kind="princess_tower") for u in range(4)]
    towers = {u["uid"] for u in units if u["kind"] != "troop"}
    monkeypatch.setattr(SU, "extract", lambda battle, memo, hit_window_ms=50: dict(units=units))
    monkeypatch.setattr(E, "require_cue_runtime", lambda: None)
    match = SimpleNamespace(_obs=(tok, mask), env=SimpleNamespace(core=SimpleNamespace(_battle=None)), side=side)
    want = E.sim_cue_rows(match)
    got = align(tok, mask, side, [(u["team"], u["x"], u["y"], cue_vector(u, u["attack"]["target"] in towers))
                                  for u in units if u["uid"] not in towers])
    assert np.array_equal(want, got)


def _ent(gen, side, x, y, raw, hp=500, mhp=500, kind=15, cid=26000000):
    return dict(category=gen, side=side, x=x, y=y, behavior_state_raw=raw, hp=hp, max_hp=mhp, kind=kind, card_id=cid,
                address=hex(gen))


def _buff(name, rem, dur, spd=0, hsp=0, **cfg):
    return dict(name=name, remaining_ms_raw=rem, duration_ms_raw=dur, shield_value_raw=0,
                config={"SpeedMultiplier": spd, "HitSpeedMultiplier": hsp, "Invisible": 0, "Shield": 0, **cfg})


def _frame(tick=1000, degraded=False):
    """My side 1 (top of the engine board). Gens: 4 my princess, 5 enemy king, 10 my Knight hitting 11, 11 enemy Knight
    with a far default target (my princess), 12 Tesla hidden, 13 Prince charging, 14 / 15 Recruits (intact / hit),
    16 Tombstone holding a target, 17 enemy Knight frozen + slowed + raged + invisible."""
    ents = [_ent(4, 1, 3500, 25500, 0, 3000, 3000, kind=13, cid=-1), _ent(5, 0, 9000, 3000, 0, 4000, 4000, kind=12, cid=-1),
            _ent(10, 1, 9000, 16000, 2), _ent(11, 0, 9000, 15000, 2), _ent(12, 1, 6000, 20000, 0),
            _ent(13, 0, 14000, 10000, 1), _ent(14, 0, 4000, 9000, 1), _ent(15, 0, 4500, 9000, 1, hp=200),
            _ent(16, 0, 9000, 6000, 0), _ent(17, 0, 12000, 14000, 1)]
    names = {4: "PrincessTower", 5: "KingTower", 10: "Knight", 11: "Knight", 12: "Tesla", 13: "Prince", 14: "Recruit",
             15: "Recruit", 16: "Tombstone", 17: "Knight"}
    buffs = {10: [_buff("IceWizardHeroSlow", 2450, 2500, -30, -30)],
             17: [_buff("Freeze", 900, 4000, -100, -100), _buff("Rage", 800, 1000, 35, 35),
                  _buff("SomeInvisibility", 999999, 999999, Invisible=1), _buff("IceWizardHeroSlow", 1000, 2500, -30, -30)]}
    att = {10: dict(target_gen=11, progress_raw=1250), 11: dict(target_gen=4, progress_raw=0), 16: dict(target_gen=10, progress_raw=0)}
    f = dict(game_tick=tick, entities=ents, cues_degraded=degraded)
    if not degraded:
        f["phase2"] = dict(valid=True, units=[dict(generation=g, name=n, buffs=buffs.get(g, [])) for g, n in names.items()])
        f["phase3"] = dict(valid=True, defs=[], bodies=[dict(generation=g, definition_id=0, attack=att.get(g)) for g in names])
    return f


def test_live_rules_on_a_synthetic_frame(table):
    c = LiveCues(table)
    prev = copy.deepcopy(_frame(998))
    next(e for e in prev["entities"] if e["category"] == 13)["y"] -= 240        # Prince: 240 mt in 2 ticks = 2 x walk
    us = {u["generation"]: u for u in c.units(_frame(1000), prev)}
    v = {g: cue_vector(u, u["target_is_tower"]) for g, u in us.items()}
    k = lambda i: [g for g in (10, 11, 12, 13, 14, 15, 16, 17) if v[g][i]]  # noqa: E731 -- gens with float i set
    assert all(v[g][0] == 1 for g in v) and us[4]["tower"] and us[5]["tower"]
    assert us[10]["state"] == "engaged" and us[10]["attack"]["target"] == 11 and us[10]["attack"]["phase"] == "hit"
    assert v[10][15] == pytest.approx(round(1250 % 1200 / 1200, 3))
    assert us[11]["attack"]["target"] is None and us[11]["state"] == "moving"      # far default target dropped
    assert us[16]["attack"]["target"] is None                                      # no attack: holds no target
    assert k(9) == [12] and us[12]["state"] == "idle"                              # Tesla hidden
    assert k(8) == [13]                                                            # Prince charging
    assert k(20) == [14]                                                           # intact Recruit = shield up
    assert k(16) == [17] and k(18) == [17] and k(19) == [17]                       # frozen / raged / invisible
    assert k(17) == [10, 17]                                                       # slowed
    tot = max(2450, table["totals"].get("IceWizardHeroSlow", 0))
    assert v[10][21] == pytest.approx(round(2450 / tot, 3))
    assert c.memo[(10, "IceWizardHeroSlow")] == tot
    c.memo[99, "Old"] = 1
    c.units(_frame(500))                                                           # clock went back: a new match
    assert (99, "Old") not in c.memo and c.last_tick == 500
    c.reset()
    assert not c.memo


def test_degraded_or_blockless_frames_give_zero_rows(table):
    c = LiveCues(table)
    tok, mask = np.zeros((64, TOK_F), np.float32), np.zeros(64, bool)
    mask[0], tok[0, 1], tok[0, 4:6] = True, 1.0, (0.5, 0.5)
    for f in (_frame(degraded=True), {k: v for k, v in _frame().items() if k != "phase3"},
              dict(_frame(), phase2=dict(valid=False, units=[]))):
        rows, log = c.rows(f, None, tok, mask, 1)
        assert rows.shape == (64, CUE_N) and not rows.any() and log == dict(degraded=True)


def test_pilot_row_follows_the_model(table):
    """No cue layer: the builder is never read (rows byte-identical with it attached). Cue layer: b['cue'] rows, and a
    refusal without a cue source."""
    f = icebow_frame()
    f.update(phase2=dict(valid=True, units=[dict(generation=5000006, name="Knight", buffs=[])]),
             phase3=dict(valid=True, defs=[], bodies=[dict(generation=5000006, definition_id=0, attack=None)]),
             cues_degraded=False)
    p = pilot(DecisionOptions())
    b0, _ = p.row(copy.deepcopy(f))
    p.cues = LiveCues(table)
    b1, _ = p.row(copy.deepcopy(f))
    assert "cue" not in b0 and b0.keys() == b1.keys()
    assert all(torch.equal(b0[k], b1[k]) for k in b0)
    assert "cue" not in p.decide(copy.deepcopy(f))
    p.model.cue_in = object()                                                      # a cue-layer checkpoint
    b2, _ = p.row(copy.deepcopy(f))
    assert b2["cue"].shape == (1, b0["tok"].shape[1], CUE_N) and b2["cue"][0, :, 0].sum() == 1   # my Knight's token
    assert p.decide(copy.deepcopy(f))["cue"]["known"] == 1
    p.cues = None
    with pytest.raises(ValueError, match="cue layer"):
        p.row(copy.deepcopy(f))


def test_live_options_file_carries_the_flag(tmp_path):
    import argparse
    from pipeline.live_options import add_live_options_arguments, parse_with_live_options
    from pipeline.decision_options import add_arguments
    path = tmp_path / "LIVE_OPTIONS"
    for text, want in (("--cue-inputs on\n", "on"), ("--log-frames\n", "off")):
        path.write_text(text)
        ap = argparse.ArgumentParser()
        add_arguments(ap)
        ap.add_argument("--cue-inputs", choices=("off", "on"), default="off")
        ap.add_argument("--log-frames", action="store_true")
        add_live_options_arguments(ap, path)
        a, _ = parse_with_live_options(ap, [])
        assert a.cue_inputs == want


def test_malformed_block_reads_no_cue(table):
    tok, mask = np.zeros((64, TOK_F), np.float32), np.zeros(64, bool)
    f = _frame()
    f["phase2"]["units"][0].pop("buffs")
    f["phase3"]["bodies"][2]["attack"] = dict(target_gen=11)        # no progress field: fine
    f["entities"][3].pop("x")                                        # a body without a position: the error path
    rows, log = LiveCues(table).rows(f, None, tok, mask, 1)
    assert not rows.any() and log["degraded"] and "KeyError" in log["error"]
