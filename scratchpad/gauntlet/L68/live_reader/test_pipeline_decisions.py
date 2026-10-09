"""L74: live_play --pipeline-decisions (the MODEL decides again while a play is tapped but unconfirmed), against test_follow_up's
fake game (measured rules: a tap is held until payable, executes 22 ticks later), and the pilot's pending view (GenPilot.row)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, play  # noqa: E402
from test_follow_up import Game  # noqa: E402  (hand Rocket 6 / Tornado 3 / Knight 3 / Log 2, next Skeletons)


class PipePilot(Pilot):
    """Decisions by call number (call 1 = play_match's warm-up): plan = {call: (hand_pos, name)}; everything else waits."""

    def __init__(self, plan):
        super().__init__()
        self.plan, self.calls, self.ticks, self.seen, self.pending, self.recorded = plan, 0, [], [], [], []

    def set_pending(self, plays):
        self.pending = list(plays)

    def decide(self, f):
        self.calls += 1
        self.ticks.append(f["game_tick"])
        self.seen.append(list(self.pending))
        d = super().decide(f)
        if self.calls not in self.plan:
            return dict(d, play=False)
        pos, name = self.plan[self.calls]
        return dict(d, hand_pos=pos, deck_index=pos, name=name, card=10 + pos, form=0, xy=(0.5, 0.6))

    def record_play(self, card, form, xy, t_sec):
        self.recorded.append((card, round(t_sec / 0.05)))


def audited(monkeypatch):
    """The shared `play` helper builds the namespace with public_audit=False: switch the decision events on the way in."""
    real = lp.play_match
    monkeypatch.setattr(lp, "play_match", lambda a, *args, **kw: (setattr(a, "public_audit", True), real(a, *args, **kw))[1])


def run(monkeypatch, tmp_path, plan, game=None, flag=True, **extra):
    audited(monkeypatch)
    game = game or Game(elixir=10.0)
    pilot = PipePilot(plan)
    monkeypatch.setattr(lp, "input_cmd", game.tap)
    frames = ((t, game.frame(t)) for t in range(150, 330, 2))
    _, ev = play(monkeypatch, tmp_path, frames=frames, pilot=pilot, pace=0.02, tap_gap_ms=0,
                 **({"pipeline_decisions": True} if flag else {}), **extra)
    return pilot, ev, game


def plays(ev):
    return [e for e in ev if e["event"] == "play"]


def test_second_decision_while_the_first_is_pending_both_confirm(monkeypatch, tmp_path):
    pilot, ev, game = run(monkeypatch, tmp_path, {2: (0, "Rocket"), 3: (1, "Tornado")})
    a, b = plays(ev)
    assert (a["name"], b["name"]) == ("Rocket", "Tornado") and not a.get("pipelined") and b["pipelined"] and b["outstanding"] == 1
    assert 0 < b["tick"] - a["tick"] <= 6                                   # the very next newest frame(s), not ~28 ticks later
    assert [t[1] for t in game.taps] == [0, 1]
    conf = [e for e in ev if e["event"] == "confirmed"]
    assert [e["name"] for e in conf] == ["Rocket", "Tornado"]
    assert ev[-1]["event"] == "end" and ev[-1]["pipelined_plays"] == 1 and ev[-1]["fails"] == 0
    # the pilot saw A as pending at the second decision (and nothing pending at the first)
    assert pilot.seen[1] == [] and [q["name"] for q in pilot.seen[2]] == ["Rocket"]
    q = pilot.seen[2][0]
    assert (q["hand_pos"], q["deck_index"], q["land"]) == (0, 0, a["tick"] + lp.PIPELINE_LAND_TICKS)


def test_never_more_than_two_outstanding_and_no_decision_at_the_cap(monkeypatch, tmp_path):
    pilot, ev, game = run(monkeypatch, tmp_path, {2: (0, "Rocket"), 3: (1, "Tornado"), 4: (2, "Knight")})
    a, b = plays(ev)[:2]
    conf = [e for e in ev if e["event"] == "confirmed"]
    assert max(len(s) for s in pilot.seen) == 1                             # a decision only ever saw ONE outstanding play
    window = [t for t in pilot.ticks if b["tick"] < t < conf[0]["tick"]]    # B tapped .. A confirmed: two outstanding
    assert window == [], window                                             # (A's confirmation frame is the first free one)
    assert not any(e.get("name") == "Knight" for e in plays(ev)[:2])
    assert len(game.taps) >= 2


def test_the_pending_slot_cannot_be_tapped_again_and_the_verdict_says_so(monkeypatch, tmp_path):
    pilot, ev, game = run(monkeypatch, tmp_path, {2: (0, "Rocket"), 3: (0, "Rocket")})     # the model re-picks the pending slot
    assert [e["name"] for e in plays(ev)] == ["Rocket"]
    blocked = [e for e in ev if e["event"] == "pipeline_blocked"]
    assert blocked and blocked[0]["why"] == "slot_busy" and blocked[0]["name"] == "Rocket"
    assert [t[1] for t in game.taps] == [0]


def test_a_second_play_the_elixir_cannot_cover_is_blocked_by_the_shared_verdict(monkeypatch, tmp_path):
    pilot, ev, game = run(monkeypatch, tmp_path, {2: (0, "Rocket"), 3: (1, "Tornado")}, game=Game(elixir=7.0))   # 6 + 3 > 7
    assert [e["name"] for e in plays(ev)][:1] == ["Rocket"]
    assert any(e["event"] == "pipeline_blocked" and e["why"] == "unaffordable" and e["name"] == "Tornado" for e in ev)
    assert [t[1] for t in game.taps][:1] == [0]


def test_a_refused_first_play_changes_nothing_the_second_stands_alone(monkeypatch, tmp_path):
    pilot, ev, game = run(monkeypatch, tmp_path, {2: (0, "Rocket"), 3: (1, "Tornado")}, game=Game(elixir=10.0, refuse=[0]),
                          early_release_margin=8)
    names = [e["name"] for e in plays(ev)]
    assert names[:2] == ["Rocket", "Tornado"]
    kinds = [(e["event"], e["name"]) for e in ev if e["event"] in ("confirmed", "unconfirmed")]
    assert ("unconfirmed", "Rocket") in kinds and ("confirmed", "Tornado") in kinds     # B landed on its own merits


def test_only_the_newest_frame_decides_under_backlog(monkeypatch, tmp_path):
    import threading
    game = Game(elixir=10.0)
    taps = []

    def tap(cmd, timeout=5):
        taps.append(cmd)
        if len(taps) == 1:
            threading.Event().wait(0.3)                                      # a slow first tap: frames pile up behind it
        return game.tap(cmd)

    def frames():
        for t in range(150, 330, 2):
            if not (160 <= t < 200):
                threading.Event().wait(0.02)
            yield t, game.frame(t)
    pilot = PipePilot({2: (0, "Rocket"), 3: (1, "Tornado")})
    audited(monkeypatch)
    monkeypatch.setattr(lp, "input_cmd", tap)
    _, ev = play(monkeypatch, tmp_path, frames=frames(), pilot=pilot, pace=0.0, tap_gap_ms=0,
                 pipeline_decisions=True)
    first_tap = next(e for e in ev if e["event"] == "tap_timing")
    assert first_tap["frame_age_backlog"] >= 5
    dec = [e for e in ev if e["event"] == "decision" and e.get("pending")]
    assert all(e["backlog"] == 0 for e in dec), [e["backlog"] for e in dec]   # a pipelined decision is always on the newest frame


def test_flag_off_never_calls_set_pending_and_keeps_the_lock(monkeypatch, tmp_path):
    pilot, ev, game = run(monkeypatch, tmp_path, {2: (0, "Rocket"), 3: (1, "Tornado")}, flag=False)
    assert pilot.seen[1:3] == [[], []] and not any(e.get("pipelined") for e in plays(ev))
    a = plays(ev)[0]
    assert not [t for t in pilot.ticks if a["tick"] < t < next(e for e in ev if e["event"] == "confirmed")["tick"]]
    assert "pipeline_decisions" not in ev[0] and "pipelined_plays" not in ev[-1]


def test_check_json_reports_the_flag_only_when_on(monkeypatch, tmp_path, capsys):
    ck = tmp_path / "m.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4, decision_options=kw["decision_options"]))
    out = []
    for extra in ([], ["--pipeline-decisions", "--pipeline-tau-delta", "0.1"]):
        monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--ckpt", str(ck)] + extra)
        assert lp.main() == 0
        out.append(json.loads(capsys.readouterr().out.strip().splitlines()[-1]))
    assert "pipeline_decisions" not in out[0] and out[1]["pipeline_decisions"] is True and out[1]["pipeline_tau_delta"] == 0.1


# ---- the pilot's pending view (GenPilot.row), on a REAL reader frame -------------------------------------------------------
REAL_FRAMES = Path(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\probe1.jsonl")
CKPT = Path(r"C:\Users\benpe\ClashBot\icebow\data\bench\rl_royale\rseries_r3c\rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt")


@pytest.fixture(scope="module")
def pilot_and_frame():
    if not (REAL_FRAMES.is_file() and CKPT.is_file()):
        pytest.skip("local data (probe1.jsonl / live checkpoint) not present")
    from pipeline.live_gen_v2 import GenPilot
    pilot = GenPilot(str(CKPT), device="cpu", gate_tau=0.35, extrapolate_ticks=24, own_effects=True)
    frame = None
    for ln in REAL_FRAMES.open():
        f = json.loads(ln)
        if f.get("battle_active") and f.get("coherent") and int(f.get("game_tick", 0)) > 150:
            vis = [p for p in f["players"] if any(i >= 0 for i in p["hand_deck_indices"])]
            if len(vis) == 1 and f["entities"]:
                frame = f
                break
    if frame is None:
        pytest.skip("no usable frame in probe1.jsonl")
    pilot.reset_match()
    pilot.observe(frame)
    return pilot, frame


def test_pending_view_hand_elixir_past_and_mask(pilot_and_frame):
    import torch
    pilot, frame = pilot_and_frame
    side = next(p["side"] for p in frame["players"] if any(i >= 0 for i in p["hand_deck_indices"]))
    me = next(p for p in frame["players"] if p["side"] == side)
    b0, i0 = pilot.row(frame)
    pilot.set_pending([])
    b1, i1 = pilot.row(frame)
    assert all(torch.equal(b0[k], b1[k]) for k in b0) and i0["costs"] == i1["costs"] and not i0.get("pending")   # none = unchanged
    pos = 0
    names = i0["names"]
    q = dict(hand_pos=pos, deck_index=me["hand_deck_indices"][pos], card=int(b0["hand_card"][0][pos]),
             form=int(b0["hand_form"][0][pos]), name=names[me["hand_deck_indices"][pos]], xy=(0.5, 0.62),
             land=int(frame["game_tick"]) + 24 - 4)                 # decided 4 ticks ago: on the look-ahead board for 4 ticks
    pilot.set_pending([q])
    b2, i2 = pilot.row(frame)
    try:
        assert i2["pending"] is True
        assert i2["costs"][pos] == float("inf")                              # the pending slot's position is never choosable
        assert i2["bs"].my_elixir < i0["bs"].my_elixir - 0.99                # minus the card's cost (>= 1)
        assert i2["hand_deck_indices"][pos] != me["hand_deck_indices"][pos]  # the view shows the next card there
        assert int(b2["hand_card"][0][pos]) != int(b0["hand_card"][0][pos])
        assert int(b2["past"][0][0][0]) == q["card"]                         # the pending play is the newest past play
        assert not torch.equal(b2["tok"], b0["tok"])                         # its body / area is on the look-ahead board
    finally:
        pilot.set_pending([])
