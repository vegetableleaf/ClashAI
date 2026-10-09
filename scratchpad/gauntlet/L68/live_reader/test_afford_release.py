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


def test_two_released_slots_both_watched(monkeypatch, tmp_path):
    """Verifier F1 repro: slot 0 played 152, released 184; slot 1 played 186, released 218; slot 0 rotates 240 ->
    slot 0's late landing is still recorded (one released tap per slot, not one in total)."""
    frames = [(t, frame(t, slot0=0 if t < 240 else 4)) for t in range(150, 260, 2)]
    pilot = SeqPilot()
    _, ev = play(monkeypatch, tmp_path, frames=frames, pilot=pilot, pace=0.05, early_release_margin=8)
    kinds = [(e["event"], e["tick"]) for e in ev if e["event"] in ("play", "unconfirmed", "late_landing")]
    assert kinds[:4] == [("play", 152), ("unconfirmed", 184), ("play", 186), ("unconfirmed", 218)], kinds
    late = [e for e in ev if e["event"] == "late_landing"]
    assert [e["tick"] for e in late] == [240] and late[0]["after_ticks"] == 88, kinds
    assert [r[3] for r in pilot.recorded] == [240 * 0.05]


def test_late_landings_count_as_confirmations(monkeypatch, tmp_path):
    """Verifier F2: every tap is released early and then lands; 5+ in a row must not stop the match, and each late
    landing counts as confirmed (fails / confirmed in the end event)."""
    hand_x = [lp.Layout(900, 1600).hand(p)[0] for p in range(4)]
    st = {"tick": 0, "due": {}, "flips": [0, 0, 0, 0]}

    def tap(cmd, timeout=5):
        pos = hand_x.index(int(cmd.split()[2].rstrip(";")))
        st["due"][pos] = st["tick"] + 40                   # lands 40 ticks after the tap: after the ~31-tick release
        return True

    def frames():
        for t in range(150, 700, 2):
            st["tick"] = t
            for p, due in list(st["due"].items()):
                if t >= due:
                    st["flips"][p] ^= 1
                    del st["due"][p]
            f = json.loads(frame(t))
            f["players"][0]["hand_deck_indices"] = [p + 4 * st["flips"][p] for p in range(4)]
            yield t, json.dumps(f) + "\n"

    class Cycle(Pilot):
        n = 0

        def decide(self, f):
            d = super().decide(f)
            d["hand_pos"], self.n = (self.n - 1) % 4, self.n + 1    # call 0 = warm-up; then slots 0, 1, 2, 3, 0, ...
            return d
    monkeypatch.setattr(lp, "input_cmd", tap)
    _, ev = play(monkeypatch, tmp_path, frames=frames(), pilot=Cycle(), pace=0.03, early_release_margin=8)
    late = [e for e in ev if e["event"] == "late_landing"]
    unconf = [e for e in ev if e["event"] == "unconfirmed"]
    end = next(e for e in ev if e["event"] == "end")
    assert len(late) >= 6 and not any(e["event"] == "stop" and e["why"] == "5_unconfirmed" for e in ev), late
    assert end["confirmed"] == len(late) + sum(e["event"] == "confirmed" for e in ev)
    assert end["fails"] == len(unconf) - len(late)


def test_check_json_reports_the_latency_options(monkeypatch, tmp_path, capsys):
    """Verifier F3: --check prints extrapolate / afford_ticks / early_release_margin / fast_input / tap_gap_ms."""
    ck = tmp_path / "m.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--ckpt", str(ck),
                                      "--extrapolate", "24", "--afford-ticks", "23", "--early-release-margin", "8",
                                      "--fast-input", "--tap-gap-ms", "0"])
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4,
                                                                           decision_options=kw["decision_options"]))
    assert lp.main() == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (out["extrapolate"], out["afford_ticks"], out["early_release_margin"], out["fast_input"],
            out["tap_gap_ms"]) == (24, 23, 8, True, 0)
