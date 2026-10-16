"""Opt-in merged reader (--reader <name> from CLASHBOT_READER_EXTRA): under --log-frames its cue blocks (phase2 /
phase3 / cues_degraded / read_us) ride on the 'frame' event and its definitions get a 'cues_defs' event even before
UI_READY_MIN_TICK; taps and decisions are byte-identical to the same frames without the blocks; the default v2 frames
add no key. Fake frames only (no device)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import play, rframe  # noqa: E402

DEFS = [{"definition_id": 26000000, "name": "Knight", "HitSpeed": 1200, "LoadTime": 700}]


def cframe(tick, defs=False, degraded=False):
    f = json.loads(rframe(tick))
    f.update(read_us=450, cues_degraded=degraded)
    if not degraded:
        f["phase2"] = {"valid": True, "own_side": 0, "units": []}
        f["phase3"] = {"valid": True, "bodies": [], "unlisted_targets": 0, "defs": DEFS if defs else []}
    return json.dumps(f) + "\n"


def test_cue_blocks_logged_taps_unchanged(monkeypatch, tmp_path):
    ticks = range(140, 330, 2)                      # defs arrive at tick 140: before any 'frame' event (tick >= 150)
    plain = [(t, rframe(t)) for t in ticks]
    cues = [(t, cframe(t, defs=t == 140, degraded=t in (200, 202))) for t in ticks]
    for d in ("plain", "cues", "nolog"):
        (tmp_path / d).mkdir()
    taps_p, ev_p = play(monkeypatch, tmp_path / "plain", frames=plain, log_frames=True)
    taps_c, ev_c = play(monkeypatch, tmp_path / "cues", frames=cues, log_frames=True)
    assert taps_c == taps_p and taps_c
    dec = lambda ev: [(e["tick"], json.dumps(e["decision"])) for e in ev if e["event"] == "decision"]  # noqa: E731
    assert dec(ev_c) == dec(ev_p)
    fr_p = [e for e in ev_p if e["event"] == "frame"]
    fr_c = [e for e in ev_c if e["event"] == "frame"]
    assert fr_p and not any(k in e for e in fr_p for k in ("phase2", "phase3", "cues_degraded", "read_us"))
    assert not any(e["event"] == "cues_defs" for e in ev_p)
    assert len(fr_c) == len(fr_p) and all(e["read_us"] == 450 for e in fr_c)
    assert {e["tick"] for e in fr_c if e["cues_degraded"]} == {200, 202}
    assert all(e["phase3"] is None for e in fr_c if e["cues_degraded"])
    assert all(e["phase2"]["valid"] and e["phase3"]["defs"] == [] for e in fr_c if not e["cues_degraded"])
    defs = [e for e in ev_c if e["event"] == "cues_defs"]
    assert [(e["tick"], e["defs"]) for e in defs] == [(140, DEFS)]
    _, ev_n = play(monkeypatch, tmp_path / "nolog", frames=cues)                 # without --log-frames: nothing
    assert not any(e["event"] in ("cues_defs", "frame") for e in ev_n)


def test_frame_extras_unchanged_for_v2_frames():
    f = json.loads(rframe(200))
    assert lp.frame_extras(f) == {"ents_state": [], "proj": [], "fx": []}
