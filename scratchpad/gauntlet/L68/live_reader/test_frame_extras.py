"""--log-frames parity extras (owner 10-16 reader upgrade): per-body state, projectiles and effects are logged from the
frame the reader already sends; taps unchanged; nothing from the players block; absent without --log-frames."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import play, rframe  # noqa: E402

ENT = {"side": 1, "x": 9000, "y": 20000, "card_id": 26000000, "hp": 900, "max_hp": 1000, "kind": 15,
       "address": "0xa1", "category": 7, "level": 11, "behavior_state_raw": 10, "evo": 0}
PROJ = {"side": 1, "x": 5000, "y": 15000, "card_id": 28000004, "target_x": 3500, "target_y": 6500, "address": "0xb1",
        "generation_key": 3, "source": "0x0", "target": "0x0", "vtable_rva": "0xdead"}
FX = {"side": 1, "x": 4000, "y": 8000, "card_id": 28000009, "remaining_ms": 7950, "level_raw": 9, "address": "0xc1",
      "generation_key": 4, "vtable_rva": "0xdead", "data_ptr": "0xbeef", "timer_ms_raw": 1, "life_override_ms_raw": 2}


def xframe(tick):
    f = json.loads(rframe(tick))
    f["players"][1]["elixir_raw"] = 31337                 # opponent private: must not reach the extras
    f.update(entities=[ENT], projectiles=[PROJ], effects=[FX])
    return json.dumps(f) + "\n"


def test_frame_extras_rows_and_no_internals():
    ex = lp.frame_extras(json.loads(xframe(200)))
    assert ex["ents_state"] == [[10, 0, 11, 7]]
    assert ex["proj"] == [[1, 5000, 15000, 28000004, 3500, 6500, "0xb1", 3, "0x0", "0x0"]]
    assert ex["fx"] == [[1, 4000, 8000, 28000009, 7950, 9, "0xc1", 4]]
    text = json.dumps(ex)
    assert "0xdead" not in text and "0xbeef" not in text and "31337" not in text
    assert lp.frame_extras({"entities": []}) == {"ents_state": [], "proj": [], "fx": []}   # v1 reader: no objects


def test_extras_only_with_log_frames_and_taps_unchanged(monkeypatch, tmp_path):
    frames = [(t, xframe(t)) for t in range(150, 330, 2)]
    (tmp_path / "off").mkdir()
    (tmp_path / "on").mkdir()
    taps_off, ev_off = play(monkeypatch, tmp_path / "off", frames=frames)
    taps_on, ev_on = play(monkeypatch, tmp_path / "on", frames=frames, log_frames=True)
    assert taps_on == taps_off and taps_on                # byte-identical inputs
    dec = lambda ev: [(e["tick"], json.dumps(e["decision"])) for e in ev if e["event"] == "decision"]  # noqa: E731
    assert dec(ev_on) == dec(ev_off)
    fr = [e for e in ev_on if e["event"] == "frame"]
    assert len(fr) >= 80 and all(len(e["ents_state"]) == len(e["ents"]) == 1 for e in fr)
    assert all(e["proj"][0][3] == 28000004 and e["fx"][0][4] == 7950 for e in fr)
    assert not any("ents_state" in e for e in ev_off)
