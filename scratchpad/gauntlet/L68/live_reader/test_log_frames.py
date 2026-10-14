"""--log-frames (owner 2026-10-14): the board 'frame' event on every reader frame without screen recording; play unchanged."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_fast_input import play  # noqa: E402


def test_frames_logged_only_with_the_flag_and_taps_unchanged(monkeypatch, tmp_path):
    taps, ev = play(monkeypatch, tmp_path)
    assert taps and not any(e["event"] == "frame" for e in ev)
    (tmp_path / "on").mkdir()
    taps_on, ev_on = play(monkeypatch, tmp_path / "on", log_frames=True)
    frames = [e for e in ev_on if e["event"] == "frame"]
    assert taps_on == taps                                    # the same inputs
    assert len(frames) >= 80 and all({"tick", "ents", "elixir", "my_side"} <= set(e) for e in frames)
    assert [e["tick"] for e in frames] == sorted(e["tick"] for e in frames)
