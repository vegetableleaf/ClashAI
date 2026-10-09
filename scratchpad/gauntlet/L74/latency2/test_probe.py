"""probe_live.probe_plan (which plays the probe picks) and analyze_probe.pairs (what the live test reads), offline."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = HERE.parents[1] / "L68/live_reader"
sys.path[:0] = [str(HERE), str(LIVE), str(HERE.parents[3])]
import analyze_probe as ap  # noqa: E402
import probe_live as pl  # noqa: E402
import test_follow_up as tf  # noqa: E402
from test_follow_up import planner  # noqa: E402,F401  (the fixture)


class Pilot(tf.PlannerPilot):
    pass


def frame(tick=700, elixir=9.0, hand=(2, 3, 0, 1), forms=None):
    f = tf.planner_frame(hand=hand)
    f["game_tick"] = tick
    f["players"][0]["elixir_raw"] = int(elixir * 1e4)
    if forms is not None:
        f["players"][0]["deck_form_flags"] = forms
    return f


def state():
    return dict(n=0, last=-10 ** 9)


def test_probe_picks_the_two_cheapest_plain_cards_and_plans_the_second(planner):
    d = {"play": False, "p_play": 0.1, "public_audit": {}}
    out = pl.probe_plan(planner, frame(), d, state(), after_ticks=4)
    # hand = Knight(3) Log(2) Rocket(6) Tornado(3): the two cheapest are Log then a 3-cost card
    assert out["name"] == "Log" and out["play"] and out["probe"] and out["xy"] == pl.CELL_A
    (fu,) = out["follow_ups"]
    assert fu["name"] in ("Knight", "Tornado") and fu["hand_pos"] != out["hand_pos"] and fu["xy"] == pl.CELL_B
    assert fu["follow"]["after_ticks"] == 4


def test_probe_stays_out_of_the_way(planner):
    d = {"play": False, "p_play": 0.1}
    s = state()
    assert pl.probe_plan(planner, frame(tick=500), d, s) is None                        # too early
    assert pl.probe_plan(planner, frame(elixir=4.0), d, s) is None                      # not enough spare elixir
    assert pl.probe_plan(planner, frame(), dict(d, play=True), s) is None               # the model plays itself
    assert pl.probe_plan(planner, frame(hand=(0, 0, 0, 2)), d, s) is None              # only one plain cheap card
    assert pl.probe_plan(planner, frame(forms=[2] * 8), d, s) is None                   # hero / evo forms are not probed
    first = pl.probe_plan(planner, frame(), d, s, every_s=45.0)
    assert first and s["n"] == 1
    assert pl.probe_plan(planner, frame(tick=700 + 100), d, s, every_s=45.0) is None    # 5 s later: too soon
    assert pl.probe_plan(planner, frame(tick=700 + 900), d, s, every_s=45.0, max_probes=1) is None   # per-match cap
    assert pl.probe_plan(planner, frame(tick=700 + 900), d, s, every_s=45.0)           # 45 s later


def test_analyzer_reads_a_pipelined_pair(monkeypatch, tmp_path):
    game = tf.Game(elixir=10.0)
    _, ev = tf.run(monkeypatch, tmp_path, game, [tf.fu_dict(after=4)])
    (pair,) = ap.pairs(ev)
    a, b = pair["a_play"], pair["b_play"]
    assert (a["name"], b["name"]) == ("Rocket", "Tornado") and pair["a_conf"] and pair["b_conf"]
    assert 4 <= b["tick"] - a["tick"] <= 6 and pair["b_conf"]["tick"] - pair["a_conf"]["tick"] <= 8
    assert not pair["cancelled"] and not pair["b_unconf"]


def test_analyzer_reports_a_cancelled_follow_up(monkeypatch, tmp_path):
    _, ev = tf.run(monkeypatch, tmp_path, tf.Game(elixir=8.0), [tf.fu_dict(after=0, within=12)])
    (pair,) = ap.pairs(ev)
    assert pair["b_play"] is None and pair["cancelled"]["why"] == "unaffordable" and pair["a_conf"]
