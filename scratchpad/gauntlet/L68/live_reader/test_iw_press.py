"""--iw-press never (owner 2026-10-14 ability A/B): the button is still watched and should_press still runs, no tap is sent."""
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, play  # noqa: E402

BUTTON = (700, 1400)


class WaitPilot(Pilot):
    gate_tau = 0.35

    def decide(self, f):
        return {"play": False, "p_play": 0.0, "gate_tau": self.gate_tau, "public_audit": {}}

    def record_ability(self, *a, **k):
        pass


def run(monkeypatch, tmp_path, blue=0.41, **extra):
    shots = []                                  # blue .41 = a real ready button (no phase 2 here: press_gate's band)
    button = SimpleNamespace(want=False, blue=blue, grey=0.0, point=BUTTON, ts=0.0, stop=lambda: None,
                             fresh_state=lambda: shots.append(1) or "ready")
    monkeypatch.setattr(lp, "HeroButton", lambda *a, **k: button)
    monkeypatch.setattr(lp, "hero_ids", lambda me: [26000000])
    monkeypatch.setattr(lp, "should_press", lambda *a, **k: (True, "test"))
    orig = lp.play_match
    monkeypatch.setattr(lp, "play_match", lambda a, *r, **k: (setattr(a, "no_ability", False), orig(a, *r, **k))[1])
    cmds, ev = play(monkeypatch, tmp_path, pilot=WaitPilot(), no_iw_pro_gate=False, **extra)
    return [c for c in cmds if c == f"input tap {BUTTON[0]} {BUTTON[1]}"], ev, shots


def test_rule_presses_and_never_only_logs(monkeypatch, tmp_path):
    taps, ev, shots = run(monkeypatch, tmp_path)                       # default: unchanged, the rule presses
    assert taps and any(e["event"] == "ability" for e in ev) and shots
    (tmp_path / "n").mkdir()
    taps, ev, shots = run(monkeypatch, tmp_path / "n", iw_press="never")
    held = [e["tick"] for e in ev if e["event"] == "ability_withheld"]
    assert taps == [] and not any(e["event"] == "ability" for e in ev)
    assert shots and held and all(b - a >= 20 for a, b in zip(held, held[1:]))   # still watched; logged <= 1/s


def test_gate_withholds_a_floor_misread_on_rule_and_head(monkeypatch, tmp_path):
    for k, extra in enumerate(({}, {"iw_press": "head"})):   # no phase 2 + blue .52 (the arena floor): never pressed
        (tmp_path / str(k)).mkdir()
        taps, ev, _ = run(monkeypatch, tmp_path / str(k), blue=0.52, **extra)
        held = [e for e in ev if e["event"] == "ability_withheld"]
        assert taps == [] and not any(e["event"] in ("ability", "ability_held") for e in ev)
        assert held and all(e["why"] == "band" and e["blue"] == 0.52 for e in held)
        assert all(b["tick"] - a["tick"] >= 20 for a, b in zip(held, held[1:]))   # <= one line per second
