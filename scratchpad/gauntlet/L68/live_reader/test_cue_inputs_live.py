"""live_play --cue-inputs (step c): load_pilot attaches the cue builder only to a cue-layer checkpoint, refuses a cue-layer
checkpoint without the flag or on a reader without cue blocks; the 'decision' event carries the cue summary only when the
decision has one; the merged reader's definitions reach the builder from every line. Fake pilots / frames, no device."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, rframe  # noqa: E402


class FakeGenPilot:
    def __init__(self, ckpt, **kw):
        self.model = SimpleNamespace(**({"cue_in": object()} if "cue" in str(ckpt) else {}))


def args(**kw):
    base = dict(device="cpu", ckpt="u250.pt", tau=.35, no_opp_counter=False, extrapolate=0, decision_seed=0,
                public_audit=False, reader="merged")
    return SimpleNamespace(**{**base, **kw})


@pytest.mark.parametrize("flag", [None, "off", "on"])
def test_no_cue_layer_flag_is_a_no_op(monkeypatch, flag):
    monkeypatch.setattr(lp, "GenPilot", FakeGenPilot)
    _, p = lp.load_pilot(args(**({} if flag is None else {"cue_inputs": flag})), {})
    assert getattr(p, "cues", None) is None


@pytest.mark.parametrize("kw,why", [({}, "cue layer"), ({"cue_inputs": "off"}, "cue layer"),
                                    ({"cue_inputs": "on", "reader": "v2"}, "cue blocks"),
                                    ({"cue_inputs": "on", "reader": "v1"}, "cue blocks")])
def test_cue_layer_refusals(monkeypatch, kw, why):
    monkeypatch.setattr(lp, "GenPilot", FakeGenPilot)
    with pytest.raises(SystemExit, match=why):
        lp.load_pilot(args(ckpt="cue.pt", **kw), {})


def test_cue_layer_with_flag_gets_the_builder(monkeypatch):
    from pipeline import live_unit_state
    monkeypatch.setattr(lp, "GenPilot", FakeGenPilot)
    monkeypatch.setattr(live_unit_state, "load_table", lambda: {"char": {}, "buffs": {}, "totals": {}})
    _, p = lp.load_pilot(args(ckpt="cue.pt", cue_inputs="on"), {})
    assert isinstance(p.cues, live_unit_state.LiveCues)
    assert lp.cue_log(p)["active"] and not lp.cue_log(SimpleNamespace(cues=None))["active"]


class CuePilot(Pilot):
    """A pilot whose decisions carry a cue summary and whose builder records every frame it is shown."""
    def __init__(self):
        super().__init__()
        self.cues = SimpleNamespace(seen=[], observe=lambda f: self.cues.seen.append(f["game_tick"]))

    def decide(self, f):
        return dict(super().decide(f), cue=dict(degraded=False, bodies=0, known=0, nz=[0] * 22))


def audited_play(monkeypatch, tmp_path, pilot):
    """test_fast_input.play with the public audit on (the 'decision' event is written only then)."""
    lines = iter([rframe(t) for t in range(140, 330, 2)])
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "adb", lambda *a, **k: "")
    monkeypatch.setattr(lp.subprocess, "Popen", lambda *a, **k: SimpleNamespace(
        stdout=lines, stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0, terminate=lambda: None))
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    lp.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
    a = SimpleNamespace(tau=.35, leak=9.5, dry_run=True, ckpt="x", extrapolate=0, no_opp_counter=True, ckpt_source="t",
                        ckpt_sha256="t", public_audit=True, menu_guard=False, no_ability=True, reader="v2",
                        interval_ms=100, max_seconds=60)
    lp.play_match(a, pilot, lp.Layout(900, 1600), "cpu", None, record=False)
    return [json.loads(x) for x in next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()]


def test_decision_event_carries_the_cue_summary(monkeypatch, tmp_path):
    ev = audited_play(monkeypatch, tmp_path, p := CuePilot())
    dec = [e for e in ev if e["event"] == "decision"]
    assert dec and all(e["decision"]["cue"]["degraded"] is False for e in dec)
    assert p.cues.seen[0] == 140                     # every reader line, before the 150-tick input guard too
    (tmp_path / "plain").mkdir()
    ev = audited_play(monkeypatch, tmp_path / "plain", Pilot())
    dec = [e for e in ev if e["event"] == "decision"]
    assert dec and all("cue" not in e["decision"] for e in dec)
    assert not any("cue_inputs" in e for e in ev if e["event"] == "start")
