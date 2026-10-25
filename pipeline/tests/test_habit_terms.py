"""L74 habit reward terms (pipeline/habit_terms.py + its rl_royale / e1_eval hooks, exploit/apply_habit_terms.py).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_habit_terms.py

Synthetic boards in our own frame (our king low: engine y < 16000 is our half; x < 9000 lane 0): an unanswered threat ->
one idle penalty on the row nearest the 4 s mark; an answered one -> none; a 6-elixir push answered with 9 -> trade -3 w;
the caps; off = no reward and the historical config hash (vs PRE, the last commit before the change, where git exists)."""
from __future__ import annotations

import copy
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import habit_terms as HT                                    # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402

PRE = "9c4efa8"
CFG = REPO / "scratchpad/gauntlet/L74/stepd/cfg"
W = {"habit_idle_w": 0.1, "habit_trade_w": 0.01, "habit_leak_w": 0.0}   # the defaults
P3 = {"habit_idle_w": 0.1, "habit_trade_w": 0.03}           # explicit weights for the logic tests
BASE = {"advantage": "gae", "league": True, "critic_warmup_updates": 5, "shaping_critic_scale": 1.6}


def _yaml(path):
    """a config as rl_royale.load_config reads it, without its file-existence checks (laptop: no pod checkpoints)."""
    import yaml
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("hero_abilities", False)
    return cfg


def board(bodies_at, t_end=600, el=5.0):
    """samples every 20 ticks 100..t_end; ``bodies_at(t)`` -> enemy bodies [(uid, name, hp, max_hp, x, y)]."""
    return [(t, el, bodies_at(t)) for t in range(100, t_end + 1, 20)]


def giant(t):                       # one full-hp Giant (5 elixir) on our half, lane 0, ticks 200..400
    return [(7, "Giant", 3000, 3000, 4000.0, 8000.0)] if 200 <= t <= 400 else []


def knights(t):                     # two Knights (3 + 3 = 6 elixir) crossing at 200, gone after 400
    return [(1, "Knight", 1000, 1000, 4000.0, 9000.0), (2, "Knight", 1000, 1000, 5000.0, 9000.0)] if 200 <= t <= 400 else []


def test_unanswered_threat_one_idle_penalty_on_the_row_nearest_4s():
    ev = HT.events(board(giant), [], low=True)
    assert ev["thr"] == 1 and ev["idle"] == [[200, 0]]
    ticks = [100, 200, 275, 300, 420]                                     # 4 s mark = 280: nearest kept row 275
    out = HT.row_terms(ev, ticks, {"habit_idle_w": 0.1, "habit_trade_w": 0.0})
    assert np.count_nonzero(out["r"]) == 1 and out["r"][2] == pytest.approx(-0.1) and out["idle"] == pytest.approx(-0.1)


def test_answered_threat_no_idle():
    ev = HT.events(board(giant), [(230, "knight_evo", 4000, 10000)], low=True)   # a play 1.5 s after onset, our half
    assert ev["thr"] == 1 and ev["idle"] == []
    assert not HT.row_terms(ev, [100, 230, 280], {"habit_idle_w": 0.1, "habit_trade_w": 0.0})["r"].any()


def test_push_value_6_answered_with_9_is_minus_3w():
    ev = HT.events(board(knights), [(210, "x_bow", 4000, 12000), (220, "knight_evo", 4000, 10000)], low=True)
    assert ev["push"] == [[200, 420, 6.0, 9.0]]                          # ends at the first clear sample >= 6 s on
    out = HT.row_terms(ev, [100, 210, 220, 400, 430], {"habit_idle_w": 0.0, "habit_trade_w": 0.03})
    assert np.count_nonzero(out["r"]) == 1 and out["r"][3] == pytest.approx(-3 * 0.03)   # the last row <= push end


def test_the_other_frame_and_a_play_on_the_enemy_half():
    flip = (lambda t: [(u, n, h, m, 18000 - x, 32000 - y) for u, n, h, m, x, y in knights(t)])   # our king high
    ev = HT.events(board(flip), [(210, "x_bow", 14000, 32000 - 12000), (220, "rocket", 9000, 32000 - 26000)], low=False)
    assert ev["push"] == [[200, 420, 6.0, 6.0]]                          # the Rocket landed on THEIR half: not spend


def test_caps_and_clip():
    p = dict(P3)
    rec = {"thr": 5, "idle": [[t, 0] for t in (100, 300, 500, 700, 900)], "push": []}
    out = HT.row_terms(rec, np.arange(0, 1200, 10), p)
    assert out["idle"] == pytest.approx(-HT.IDLE_MATCH_CAP) and out["r"].sum() == pytest.approx(-0.3)
    assert np.count_nonzero(out["r"]) == 3
    rec = {"thr": 0, "idle": [], "push": [[t, t + 200, 20.0, 0.0] for t in (100, 400)]
           + [[t, t + 200, 3.0, 20.0] for t in (700, 1000, 1300)]}
    out = HT.row_terms(rec, np.arange(0, 1600, 10), p)
    e = out["r"][np.nonzero(out["r"])]
    np.testing.assert_allclose(e, [-0.15, -0.15])                       # under-paid pushes earn 0; clip -5 x w; budget 0.3 used up
    assert np.abs(out["r"]).sum() <= HT.TRADE_MATCH_CAP + 1e-12
    assert HT.bound(p) == pytest.approx(0.6) and HT.bound({**p, "habit_trade_w": 0.0}) == pytest.approx(0.3)


def test_config_validation_and_bound_check():
    for off in (None, False):
        assert HT.habit_cfg({**BASE, "habit_reward": off}) is None
    assert HT.habit_cfg(BASE) is None
    assert HT.habit_cfg({**BASE, "habit_reward": True}) == W
    for bad in ({"habit_idle_w": 0.1}, {"habit_reward": True, "habit_hazard_w": 0.02}, {"habit_reward": "yes"},
                {"habit_reward": True, "habit_trade_w": -1}, {"habit_reward": True, "league": False},
                {"habit_reward": True, "advantage": "match_loo"}):
        with pytest.raises(SystemExit):
            HT.habit_cfg({**BASE, **bad})
    RL.adv_cfg({**BASE, "habit_reward": True})                           # 1.6 >= 1 + 0.3 + 0.3
    with pytest.raises(SystemExit):
        RL.adv_cfg({**BASE, "habit_reward": True, "shaping_critic_scale": 1.5})
    RL.adv_cfg({**BASE, "habit_reward": True, "habit_trade_w": 0.0, "shaping_critic_scale": 1.3})


def test_off_same_hash_and_habc_is_the_parent_plus_habit_keys():
    for s in (74, 75, 76):
        par = _yaml(CFG / f"drift_cal30_s{s}.yaml")
        hab = _yaml(CFG / f"drift_habc_s{s}.yaml")
        h = RL.config_sha(par)
        for off in (None, False):
            assert RL.config_sha({**par, "habit_reward": off}) == h
        assert HT.habit_cfg(hab) == W and RL.config_sha(hab) != h
        assert RL.config_sha({**hab, "habit_idle_w": None}) == RL.config_sha(hab)          # implicit = explicit default
        back = {k: v for k, v in hab.items() if k not in HT.KEYS}
        assert RL.config_sha({**back, "shaping_critic_scale": 1.5}) == h                   # nothing else differs
    assert RL.actor_cfg({**hab, "grid": "floor", "habit_track": True}, "rollout", 0, "cpu")["habit_track"] is True
    assert "habit_track" not in RL.actor_cfg({**par, "grid": "floor"}, "rollout", 0, "cpu")
    assert "habit_track" not in RL.actor_cfg({**hab, "grid": "floor", "habit_track": True}, "screen", 0, "cpu")


def test_hash_matches_the_pre_change_trainer():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"git unavailable: {exc}")
    if src.returncode:
        pytest.skip(f"git show {PRE} failed (no repo here?)")
    pre = types.ModuleType("rl_royale_pre_habit")
    pre.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_habit", "exec"), pre.__dict__)
    for y in (REPO / "pipeline/rl_royale.yaml", CFG / "drift_cal30_s74.yaml"):
        cfg = _yaml(y)
        assert RL.config_sha(cfg) == pre.config_sha(cfg), y.name


def test_collate_off_unchanged_on_adds_exactly_the_terms():
    from pipeline.tests.test_rl_royale import _results, _tiny_model
    res = _results(_tiny_model(0), [(0, 0, 40, "win"), (0, 1, 30, "loss")], seed=3, all_allowed=True)
    for r in res:
        n = len(r["traj"]["played"])
        r["traj"]["tick"] = np.arange(n, dtype=np.int64) * 10 + 100
        r["plays"] = []
        r["habit"] = {"thr": 1, "idle": [[150, 0]], "push": [[120, 300, 6.0, 9.0]], "samples": 10}
    B0, st0 = RL.collate(copy.deepcopy(res), advantage="gae")
    B1, st1 = RL.collate(copy.deepcopy(res), advantage="gae", habit=None)
    assert st1 == st0 and all(np.array_equal(B0[k], B1[k]) for k in B0) and "phi" not in B1
    B2, st2 = RL.collate(copy.deepcopy(res), advantage="gae", habit=W)
    assert (B2["r_step"] - B0["r_step"]).sum() == pytest.approx(2 * (-0.1 - 3 * W["habit_trade_w"]))
    assert not B2["phi"].any() and st2["habit"]["idle_r_mean"] == pytest.approx(-0.1)
    assert all(np.array_equal(B0[k], B2[k]) for k in B0 if k != "r_step")
    bare = copy.deepcopy(res)
    del bare[0]["habit"]
    with pytest.raises(ValueError):
        RL.collate(bare, advantage="gae", habit=W)


def test_selfplay_wiring_identical_play_and_the_elixir_the_decision_saw():
    """The real SelfPlayMatch on test_league's fake env: the record only with habit_track, every traj array byte-identical
    either way, samples >= HAB_EVERY apart, each sample's elixir = the one its decision's BoardState saw (extrapolated)."""
    from pipeline import e1_eval as E
    from pipeline.tests import test_league as TL
    seen, orig = {}, E.SelfPlaySide.prepare

    def prep(self):
        out = orig(self)
        if self.cfg.get("record"):
            seen[int(self._cur[0])] = float(self._cur[1].my_elixir)
        return out

    learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
    jobs = [(0, TL._spec(0, "snapA", 0), 0, {"rollout_index": 0, "update": 0})]

    def run(**kw):
        spy = []
        res, _ = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False))},
                         TL._cfg(record_tick=True, extrapolate_ticks=26, **kw), n=1, spy=spy)
        return res[0], spy[0]
    E.SelfPlaySide.prepare = prep
    try:
        on, m = run(habit_track=True)
        off, _ = run()
    finally:
        E.SelfPlaySide.prepare = orig
    assert "habit" not in off and on["habit"]["samples"] == len(m.habit.smp) >= 3
    assert sorted(on["traj"]) == sorted(off["traj"]) and on["plays"] == off["plays"]
    for k in off["traj"]:
        assert off["traj"][k].tobytes() == on["traj"][k].tobytes(), k
    t = [s[0] for s in m.habit.smp]
    assert all(b - a >= HT.HAB_EVERY for a, b in zip(t, t[1:]))
    assert any(abs(s[1] - 7.0) > 1e-9 for s in m.habit.smp[1:])           # the extrapolated regen is in
    for tk, el, _ in m.habit.smp:
        assert el == pytest.approx(seen[tk], abs=1e-9)


def test_leak_wasted_elixir_at_full():
    """succ48 10-23: habit_leak_w x elixir regenerated while full (both ends of a sample gap at >= FULL_E), capped."""
    from pipeline.opp_elixir_count import regen_between
    smp = [(t, el, []) for t, el in ((100, 8.0), (140, 10.0), (180, 10.0), (220, 10.0), (260, 6.0), (300, 10.0))]
    ev = HT.events(smp, [], low=True)
    assert [x[0] for x in ev["leak"]] == [180, 220]                       # gaps 140-180 and 180-220 are full at both ends
    wasted = regen_between(140, 220)
    assert sum(x[1] for x in ev["leak"]) == pytest.approx(wasted, abs=1e-3)
    p = {**W, "habit_idle_w": 0.0, "habit_trade_w": 0.0, "habit_leak_w": 0.02}
    out = HT.row_terms(ev, [100, 150, 200, 250], p)
    assert out["leak"] == pytest.approx(-0.02 * wasted, abs=1e-4) and out["leak_e"] == pytest.approx(wasted, abs=1e-3)
    assert out["r"][1] < 0 and out["r"][2] < 0 and out["r"][0] == 0      # charged to the row at / before each gap end
    big = {"thr": 0, "idle": [], "push": [], "leak": [[t, 5.0] for t in range(100, 3000, 100)]}   # 2.9 > any cap
    assert HT.row_terms(big, np.arange(0, 3000, 10), p)["leak"] == pytest.approx(-HT.LEAK_MATCH_CAP)
    assert HT.bound(p) == pytest.approx(HT.LEAK_MATCH_CAP)
    off = HT.canonical({"habit_reward": True})
    assert "habit_leak_w" not in off and HT.canonical({"habit_reward": True, "habit_leak_w": 0.02})["habit_leak_w"] == 0.02
