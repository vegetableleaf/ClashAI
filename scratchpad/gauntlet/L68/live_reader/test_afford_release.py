"""L74: live_play --early-release-margin (release_ticks, early unconfirmed, late landing) and --afford-ticks wiring."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, play  # noqa: E402


def frame(tick, slot0=0, elixir_raw=80000):
    me = {"side": 0, "hand_deck_indices": [slot0, 1, 2, 3], "elixir_raw": elixir_raw, "deck_card_ids": [26000000] * 8,
          "deck_form_flags": [0] * 8}
    opp = dict(me, side=1, hand_deck_indices=[-1] * 4)
    return json.dumps({"battle_active": True, "coherent": True, "game_tick": tick, "sample_monotonic_us": tick * 50000,
                       "players": [me, opp], "entities": []}) + "\n"


def test_release_ticks_expectation_plus_margin_capped():
    assert lp.release_ticks(8.0, "Knight", 1000, 2.1, 8) == 3 + 22 + 8      # affordable: arrival rounds up
    need = next(k for k in range(61) if 2.5 + lp_regen(1000, k) >= 3)         # Knight short by 0.5 elixir in 1x
    assert lp.release_ticks(2.5, "Knight", 1000, 2.1, 8) == need + 22 + 8
    assert lp.release_ticks(0.0, "Xbow", 1000, 2.1, 8) == lp.CONFIRM_TICKS     # never later than the old lock


def lp_regen(t, k):
    from pipeline.opp_elixir_count import regen_between
    return regen_between(t, t + k)


class SeqPilot(Pilot):
    """Plays Knight from hand position 0 first (after the warm-up call), then from position 1."""
    def __init__(self):
        super().__init__()
        self.n, self.recorded = 0, []

    def decide(self, f):
        d = super().decide(f)
        d["hand_pos"] = 0 if self.n < 2 else 1          # call 0 = play_match's warm-up forward
        self.n += 1
        return d

    def record_play(self, *a):
        self.recorded.append(a)


def test_default_lock_is_unchanged(monkeypatch, tmp_path):
    _, ev = play(monkeypatch, tmp_path, frames=[(t, frame(t)) for t in range(150, 330, 2)])
    gaps = [u["tick"] - p["tick"] for p, u in zip([e for e in ev if e["event"] == "play"],
                                                   [e for e in ev if e["event"] == "unconfirmed"])]
    assert gaps and all(g == lp.CONFIRM_TICKS + 2 for g in gaps), gaps     # first frame past 60 ticks
    assert ev[0]["early_release_margin"] is None and ev[0]["afford_ticks"] is None


def test_early_release_then_late_landing_is_recorded(monkeypatch, tmp_path):
    frames = [(t, frame(t, slot0=0 if t < 200 else 4)) for t in range(150, 260, 2)]
    pilot = SeqPilot()
    _, ev = play(monkeypatch, tmp_path, frames=frames, pilot=pilot, pace=0.05, early_release_margin=8)
    kinds = [(e["event"], e["tick"]) for e in ev if e["event"] in ("play", "unconfirmed", "late_landing")]
    # affordable Knight, near-instant fake tap: release = ceil(arrival) 0-1 + 22 + 8 -> unconfirmed at the first frame past it
    assert kinds[:4] == [("play", 152), ("unconfirmed", 184), ("play", 186), ("late_landing", 200)], kinds
    late = next(e for e in ev if e["event"] == "late_landing")
    assert late["after_ticks"] == 48 and late["release_ticks"] in (30, 31)        # ceil(arrival) of the fake tap: 0-1
    assert pilot.recorded and pilot.recorded[0][3] == 200 * 0.05          # the late landing's tick, as confirmations


def test_retap_of_the_released_slot_is_not_a_late_landing(monkeypatch, tmp_path):
    frames = [(t, frame(t, slot0=0 if t < 200 else 4)) for t in range(150, 260, 2)]
    _, ev = play(monkeypatch, tmp_path, frames=frames, pace=0.05, early_release_margin=8)    # Pilot: always position 0
    assert not any(e["event"] == "late_landing" for e in ev)
    assert any(e["event"] == "confirmed" and e["tick"] == 200 for e in ev)


def test_afford_ticks_reaches_the_pilot(monkeypatch):
    from pipeline.live_gen import GenPilot
    monkeypatch.setattr(lp, "GenPilot", lambda *a, **k: SimpleNamespace())
    a = SimpleNamespace(device="cpu", ckpt="x", tau=.35, no_opp_counter=True, extrapolate=26, decision_seed=0,
                        public_audit=False, afford_ticks=23)
    monkeypatch.setattr("pipeline.decision_options.options_from_config", lambda c: None)
    _, pilot = lp.load_pilot(a, None)
    assert pilot.afford_ticks == 23
    _, pilot = lp.load_pilot(SimpleNamespace(**dict(vars(a), afford_ticks=None)), None)
    assert not hasattr(pilot, "afford_ticks") and GenPilot.afford_ticks is None    # class default = unchanged rule
