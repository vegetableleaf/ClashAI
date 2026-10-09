"""L74 latency2: --follow-up-taps (a planned second play tapped while the first is still unconfirmed): the pure verdict,
the pilot's plan_follow_up, and play_match against a fake game that follows the measured rules (a tap is held until it
can be paid, up to ~22 ticks, then executes 22 ticks later: scratchpad/gauntlet/L74/latency/afford_arrival.txt)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, play  # noqa: E402
from pipeline.opp_elixir_count import regen_between  # noqa: E402

NAMES = ["Rocket", "Tornado", "Knight", "Log", "Skeletons", "Knight", "Knight", "Knight"]    # deck order; costs 6/3/3/2/1
LAY = lp.Layout(900, 1600)
HAND_X = [LAY.hand(p)[0] for p in range(4)]


def fu_dict(pos=1, name="Tornado", after=4, within=20, afford=None, require_first=True, deck_index=None):
    return dict(play=True, p_play=0.9, hand_pos=pos, deck_index=pos if deck_index is None else deck_index, card=7, form=0,
                name=name, xy=(0.5, 0.6),
                follow=dict(after_ticks=after, within_ticks=within, afford_ticks=afford, require_first=require_first))


def sched_entry(d, first=None, tick0=100):
    fw = d["follow"]
    return dict(d=d, first=first, tick0=tick0, due=tick0 + fw["after_ticks"], expire=tick0 + fw["after_ticks"] + fw["within_ticks"])


def me_at(elixir, hand=(0, 1, 2, 3)):
    return {"hand_deck_indices": list(hand), "elixir_raw": int(elixir * 1e4)}


def pend(pos, name):
    return {"d": {"hand_pos": pos, "name": name}}


# ---- follow_verdict (pure) ---------------------------------------------------------------------------------------------
def test_verdict_waits_until_due_then_fires_when_both_are_paid():
    fu = sched_entry(fu_dict(after=4))                                       # Tornado (3) behind a pending Rocket (6)
    assert lp.follow_verdict(fu, 103, me_at(9.5), [pend(0, "Rocket")]) == ("wait", "early")
    act, reserved = lp.follow_verdict(fu, 104, me_at(9.5), [pend(0, "Rocket")])
    assert act == "fire" and reserved == 6.0                                  # 9.5 + regen - 6 >= 3


def test_verdict_counts_the_elixir_of_every_unconfirmed_tap():
    fu = sched_entry(fu_dict(after=0))
    # 8 elixir pays Rocket (6) OR Tornado (3) but not both: without the reservation it would fire (8 >= 3)
    assert lp.follow_verdict(fu, 100, me_at(8.0), [pend(0, "Rocket")]) == ("wait", "unaffordable")
    assert lp.follow_verdict(fu, 100, me_at(8.0), [])[0] == "fire"            # nothing pending: only its own cost counts
    # exactly enough with the regeneration inside the horizon: 8.0 + regen(6 ticks) = 8.107 -> not 9
    assert lp.follow_verdict(fu, 100, me_at(8.95), [pend(0, "Rocket")])[0] == "fire"     # 8.95 + 6/56 >= 9
    assert lp.follow_verdict(fu, 100, me_at(8.80), [pend(0, "Rocket")])[0] == "wait"


def test_verdict_afford_horizon_is_per_follow_up():
    short = sched_entry(fu_dict(after=0, afford=0))
    long_ = sched_entry(fu_dict(after=0, afford=20))
    me = me_at(8.7)                                                           # short of 9 by 0.3 = 17 ticks at 1x
    assert lp.follow_verdict(short, 100, me, [pend(0, "Rocket")]) == ("wait", "unaffordable")
    assert lp.follow_verdict(long_, 100, me, [pend(0, "Rocket")])[0] == "fire"


def test_verdict_never_fires_late_and_reports_what_held_it():
    fu = sched_entry(fu_dict(after=0, within=10))
    assert lp.follow_verdict(fu, 110, me_at(8.0), [pend(0, "Rocket")]) == ("wait", "unaffordable")
    assert lp.follow_verdict(fu, 111, me_at(10.0), []) == ("cancel", "late")
    fu["blocked"] = "unaffordable"
    assert lp.follow_verdict(fu, 111, me_at(10.0), []) == ("cancel", "unaffordable")


def test_verdict_cancels_when_the_first_play_was_refused_unless_told_not_to():
    first = {"state": "unconfirmed"}
    assert lp.follow_verdict(sched_entry(fu_dict(), first), 100, me_at(10), []) == ("cancel", "first_unconfirmed")
    keep = sched_entry(fu_dict(require_first=False), first)
    assert lp.follow_verdict(keep, 104, me_at(10), [])[0] == "fire"
    assert lp.follow_verdict(sched_entry(fu_dict(after=0), {"state": "confirmed"}), 100, me_at(10), [])[0] == "fire"


def test_verdict_never_taps_a_slot_that_changed_or_is_busy_and_respects_the_cap():
    fu = sched_entry(fu_dict(pos=1, deck_index=1, after=0))
    assert lp.follow_verdict(fu, 100, me_at(10, hand=(0, 5, 2, 3)), [pend(0, "Rocket")]) == ("cancel", "slot_changed")
    assert lp.follow_verdict(fu, 100, me_at(10), [pend(1, "Tornado")]) == ("cancel", "slot_busy")
    full = [pend(0, "Rocket"), pend(2, "Knight")]
    assert len(full) == lp.FOLLOW_MAX_OUT
    assert lp.follow_verdict(fu, 100, me_at(10), full) == ("wait", "outstanding")


# ---- the pilot's plan_follow_up --------------------------------------------------------------------------------------
class PlannerPilot:
    from pipeline.live_gen_v2 import FollowUpPlanner as _P
    plan_follow_up = _P.plan_follow_up

    def _card(self, name):
        return 100 + NAMES.index(name)


def planner_frame(hand=(0, 1, 2, 3)):
    me = {"side": 0, "hand_deck_indices": list(hand), "deck_card_ids": list(range(8)), "deck_form_flags": [0, 0, 0, 0, 0, 0, 2, 0],
          "elixir_raw": 90000, "next_deck_index": 4}
    return {"players": [me, dict(me, side=1, hand_deck_indices=[-1] * 4)], "entities": [], "game_tick": 300}


@pytest.fixture
def planner(monkeypatch):
    import pipeline.live_gen_v2 as g2
    import pipeline.live_mem as lm
    monkeypatch.setattr(lm, "deck_of", lambda frame, side: (None, NAMES))
    monkeypatch.setattr(g2, "my_side_of", lambda frame: 0)
    return PlannerPilot()


def test_plan_follow_up_resolves_the_card_in_the_current_hand(planner):
    first = {"hand_pos": 0, "p_play": 0.8}
    d = planner.plan_follow_up(planner_frame(), first, "tornado", (0.25, 0.5), after_ticks=6)
    assert (d["hand_pos"], d["deck_index"], d["name"], d["card"], d["form"]) == (1, 1, "Tornado", 101, 0)
    assert d["xy"] == (0.25, 0.5) and d["play"] and d["p_play"] == 0.8
    assert d["follow"] == dict(after_ticks=6, within_ticks=20, afford_ticks=None, require_first=True)
    # form comes from the deck slot (hero / evo flags), not the hand position
    assert planner.plan_follow_up(planner_frame(hand=(0, 6, 2, 3)), first, "Knight", (0.5, 0.5), 3)["form"] in (0, 2)


def test_plan_follow_up_refuses_what_cannot_be_pipelined(planner):
    first = {"hand_pos": 0, "p_play": 0.8}
    assert planner.plan_follow_up(planner_frame(), first, "Tornado", (0.5, 0.5), 4)["hand_pos"] == 1
    assert planner.plan_follow_up(planner_frame(), {"hand_pos": 1, "p_play": 0.8}, "Tornado", (0.5, 0.5), 4) is None   # first's own slot
    assert planner.plan_follow_up(planner_frame(), first, "Skeletons", (0.5, 0.5), 4) is None    # next card, not in hand
    assert planner.plan_follow_up(planner_frame(), first, "Rocket", (0.5, 0.5), 4) is None       # only in first's slot
    with pytest.raises(ValueError):
        planner.plan_follow_up(planner_frame(), first, "Tornado", (1.5, 0.5), 4)
    with pytest.raises(ValueError):
        planner.plan_follow_up(planner_frame(), first, "Tornado", (0.5, 0.5), -1)


# ---- play_match against a fake game ----------------------------------------------------------------------------------
COST = {"Rocket": 6.0, "Tornado": 3.0, "Knight": 3.0, "Log": 2.0, "Skeletons": 1.0}


class Game:
    """Elixir regenerates; a tap is accepted when the elixir left after every earlier accepted tap covers it, or can within
    22 ticks (else refused); it executes 22 ticks after acceptance: elixir paid, the hand slot rotates."""

    def __init__(self, elixir=10.0, refuse=(), rotate=None):
        self.t, self.el, self.hand, self.nxt = 148, float(elixir), [0, 1, 2, 3], 4
        self.queue, self.taps, self.refuse, self.rotate = [], [], set(refuse), dict(rotate or {})

    def tap(self, cmd, timeout=5):
        xy = re.findall(r"input tap (\d+) (\d+)", cmd)
        if len(xy) != 2 or int(xy[0][0]) not in HAND_X:
            return True
        pos = HAND_X.index(int(xy[0][0]))
        cost = COST[NAMES[self.hand[pos]]]
        free = self.el - sum(c for _, _, c in self.queue)
        need = next((k for k in range(40) if free + regen_between(self.t, self.t + k) >= cost), 99)
        self.taps.append((self.t, pos, need, pos in self.refuse or need > 22))
        if pos not in self.refuse and need <= 22:
            self.queue.append((self.t + need + 22, pos, cost))
        return True

    def advance(self, t):
        while self.t < t:
            self.t += 1
            self.el = min(10.0, self.el + regen_between(self.t - 1, self.t))
            for ex, pos, cost in [q for q in self.queue if q[0] <= self.t]:
                self.queue.remove((ex, pos, cost))
                self.el -= cost
                self.hand[pos], self.nxt = self.nxt, self.hand[pos]
            for pos, at in list(self.rotate.items()):
                if self.t >= at:
                    self.hand[pos], self.nxt = self.nxt, self.hand[pos]
                    del self.rotate[pos]

    def frame(self, t):
        self.advance(t)
        me = {"side": 0, "hand_deck_indices": list(self.hand), "next_deck_index": self.nxt,
              "elixir_raw": int(self.el * 1e4), "deck_card_ids": list(range(8)), "deck_form_flags": [0] * 8}
        return json.dumps({"battle_active": True, "coherent": True, "game_tick": t, "sample_monotonic_us": t * 50000,
                           "players": [me, dict(me, side=1, hand_deck_indices=[-1] * 4)], "entities": []}) + "\n"


class ComboPilot(Pilot):
    """Plays Rocket (slot 0) once, asking for follow-ups; the warm-up call and every later decision wait."""

    def __init__(self, follow_ups):
        super().__init__()
        self.follow_ups, self.calls, self.record, self.ticks = follow_ups, 0, [], []

    def decide(self, f):
        self.calls += 1
        self.ticks.append(f["game_tick"])
        d = super().decide(f)
        if self.calls == 2:                               # call 1 = play_match's warm-up
            return dict(d, hand_pos=0, deck_index=0, name="Rocket", card=1, **({"follow_ups": self.follow_ups} if self.follow_ups else {}))
        return dict(d, play=False)

    def record_play(self, card, form, xy, t_sec):
        self.record.append((card, round(t_sec / 0.05)))


def run(monkeypatch, tmp_path, game, follow_ups, flag=True, **extra):
    pilot = ComboPilot(follow_ups)
    monkeypatch.setattr(lp, "input_cmd", game.tap)
    frames = ((t, game.frame(t)) for t in range(150, 330, 2))
    _, ev = play(monkeypatch, tmp_path, frames=frames, pilot=pilot, pace=0.02, tap_gap_ms=0,
                 **({"follow_up_taps": True} if flag else {}), **extra)
    return pilot, ev


def kinds(ev, *names):
    return [(e["event"], e["tick"]) for e in ev if e["event"] in names]


def test_second_tap_goes_out_while_the_first_is_pending_and_both_confirm(monkeypatch, tmp_path):
    game = Game(elixir=10.0)
    pilot, ev = run(monkeypatch, tmp_path, game, [fu_dict(after=4)])
    plays = [e for e in ev if e["event"] == "play"]
    assert [e["name"] for e in plays] == ["Rocket", "Tornado"]
    a, b = plays
    assert not a.get("follow_up") and b["follow_up"] is True
    assert 4 <= b["tick"] - a["tick"] <= 6 and b["gap_ticks"] == b["tick"] - a["tick"]    # first frame at/after +4
    assert b["outstanding"] == 1 and b["reserved_elixir"] == 6.0 and b["elixir"] + 0.01 >= 9
    assert [t[1] for t in game.taps] == [0, 1]                                            # Rocket slot, then Tornado slot
    assert game.taps[1][0] - game.taps[0][0] <= 6                                         # tapped ticks, not ~28, later
    conf = [e for e in ev if e["event"] == "confirmed"]
    assert [e["name"] for e in conf] == ["Rocket", "Tornado"] and conf[1].get("follow_up") is True
    assert conf[1]["tick"] - conf[0]["tick"] <= 8                                         # landings ~ the tap gap apart
    end = ev[-1]
    assert end["event"] == "end" and end["played"] == 2 and end["confirmed"] == 2 and end["fails"] == 0
    assert end["follow_ups_fired"] == 1 and end["follow_ups_cancelled"] == 0 and end["follow_ups_unfired"] == 0
    assert not [t for t in pilot.ticks if a["tick"] < t <= conf[1]["tick"]]               # no decision while any tap pends
    assert [r[0] for r in pilot.record] == [1, 7]                                         # both recorded, Rocket first


def test_no_decision_is_made_while_a_follow_up_waits_for_its_tick(monkeypatch, tmp_path):
    game = Game(elixir=10.0)
    pilot, ev = run(monkeypatch, tmp_path, game, [fu_dict(after=60, within=10)])           # due after the Rocket confirmed
    plays = [e for e in ev if e["event"] == "play"]
    assert [e["name"] for e in plays] == ["Rocket", "Tornado"] and plays[1]["outstanding"] == 0
    assert plays[1]["tick"] - plays[0]["tick"] in (60, 61, 62)
    assert not [t for t in pilot.ticks if plays[0]["tick"] < t <= plays[1]["tick"]]       # the wait blocked every decision


def test_unaffordable_second_tap_waits_then_is_cancelled_and_nothing_is_double_spent(monkeypatch, tmp_path):
    game = Game(elixir=8.0)                       # pays Rocket or Tornado, not both within the horizon
    pilot, ev = run(monkeypatch, tmp_path, game, [fu_dict(after=0, within=12)])
    assert [e["name"] for e in ev if e["event"] == "play"] == ["Rocket"]
    canc = [e for e in ev if e["event"] == "follow_up_cancelled"]
    assert len(canc) == 1 and canc[0]["why"] == "unaffordable" and canc[0]["waited_ticks"] >= 12
    assert [t[1] for t in game.taps] == [0]
    assert ev[-1]["follow_ups_cancelled"] == 1 and ev[-1]["fails"] == 0


def test_refused_first_play_cancels_a_follow_up_that_has_not_fired(monkeypatch, tmp_path):
    game = Game(elixir=10.0, refuse=[0])           # the game drops the Rocket tap: it never confirms
    pilot, ev = run(monkeypatch, tmp_path, game, [fu_dict(after=50, within=30)], early_release_margin=8)
    assert [e["name"] for e in ev if e["event"] == "play"] == ["Rocket"]
    assert [e["event"] for e in ev if e["event"] in ("unconfirmed", "follow_up_cancelled")] == ["unconfirmed", "follow_up_cancelled"]
    assert next(e for e in ev if e["event"] == "follow_up_cancelled")["why"] == "first_unconfirmed"
    assert [t[1] for t in game.taps] == [0]


def test_follow_up_whose_slot_changed_is_cancelled(monkeypatch, tmp_path):
    game = Game(elixir=10.0, rotate={1: 160})      # the Tornado leaves slot 1 before its tick
    _, ev = run(monkeypatch, tmp_path, game, [fu_dict(after=30, within=10)])
    assert [e["name"] for e in ev if e["event"] == "play"] == ["Rocket"]
    assert next(e for e in ev if e["event"] == "follow_up_cancelled")["why"] == "slot_changed"
    assert [t[1] for t in game.taps] == [0]


def test_flag_off_ignores_follow_ups_and_matches_a_run_without_them(monkeypatch, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    with_f = run(monkeypatch, tmp_path / "a", Game(), [fu_dict(after=4)], flag=False)[1]
    without = run(monkeypatch, tmp_path / "b", Game(), None, flag=False)[1]
    ignored = [e for e in with_f if e["event"] == "follow_up_ignored"]
    assert len(ignored) == 1 and ignored[0]["why"] == "flag_off" and ignored[0]["names"] == ["Tornado"]

    def strip(ev):          # log lines without wall-clock fields and the ignore note
        drop = {"t_dev", "decide_ms", "tap_ms", "recv_age_ms", "sample_age_ms", "tap_end_ms", "latency_s", "seconds",
                "frame_age_backlog", "backlog"}
        return [{k: v for k, v in e.items() if k not in drop} for e in ev
                if e["event"] not in ("follow_up_ignored", "reader_closed")]      # reader_closed: a thread race
    assert strip(with_f) == strip(without)
    assert "follow_up_taps" not in with_f[0] and "follow_ups_fired" not in with_f[-1]


def test_dry_run_logs_the_plan_and_taps_nothing(monkeypatch, tmp_path):
    game = Game()
    real = lp.play_match      # the shared `play` helper builds the namespace with dry_run=False: flip it on the way in
    monkeypatch.setattr(lp, "play_match", lambda a, *args, **kw: (setattr(a, "dry_run", True), real(a, *args, **kw))[1])
    _, ev = run(monkeypatch, tmp_path, game, [fu_dict(after=4)])
    assert game.taps == [] and [e["name"] for e in ev if e["event"] == "play"] == ["Rocket"]
    assert [e["why"] for e in ev if e["event"] == "follow_up_ignored"] == ["dry_run"]


def test_tap_timeout_on_the_follow_up_stops_the_match(monkeypatch, tmp_path):
    game = Game()
    calls = []

    def tap(cmd, timeout=5):
        calls.append(cmd)
        return len(calls) < 2                   # the first tap passes, the follow-up's times out
    pilot = ComboPilot([fu_dict(after=2)])
    monkeypatch.setattr(lp, "input_cmd", tap)
    frames = ((t, game.frame(t)) for t in range(150, 330, 2))
    _, ev = play(monkeypatch, tmp_path, frames=frames, pilot=pilot, pace=0.02, tap_gap_ms=0, follow_up_taps=True)
    stop = [e for e in ev if e["event"] == "stop"]
    assert stop and stop[0]["why"] == "tap_timeout" and stop[0].get("follow_up") is True and len(calls) == 2


def test_check_json_reports_the_flag_only_when_it_is_on(monkeypatch, tmp_path, capsys):
    ck = tmp_path / "m.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4, decision_options=kw["decision_options"]))
    out = []
    for extra in ([], ["--follow-up-taps"]):
        monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--ckpt", str(ck)] + extra)
        assert lp.main() == 0
        out.append(json.loads(capsys.readouterr().out.strip().splitlines()[-1]))
    assert "follow_up_taps" not in out[0] and out[1]["follow_up_taps"] is True
