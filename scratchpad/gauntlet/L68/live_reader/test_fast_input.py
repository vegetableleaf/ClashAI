"""L74 latency: the persistent-shell input path (fake adb, no device) and live_play's tap command / timing fields."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fast_input as fi  # noqa: E402
import live_play as lp  # noqa: E402

# a stand-in for `adb shell`: reads command lines from stdin, logs them, echoes the marker like the device shell
FAKE_ADB = r'''
import re, sys
mode, log = sys.argv[1], sys.argv[2]
if mode == "dead":
    sys.exit(0)
for line in sys.stdin.buffer:
    open(log, "ab").write(line)
    if mode == "hang":
        continue
    m = re.search(rb"echo (__fi\d+__)\n$", line)
    if m:
        sys.stdout.buffer.write(b"some input output\n" + m.group(1) + b"\r\n")   # adb may add \r; noise first
        sys.stdout.buffer.flush()
'''


def shell(tmp_path, mode):
    script = tmp_path / "fake_adb.py"
    script.write_text(FAKE_ADB)
    log = tmp_path / f"{mode}.log"
    # PersistentShell appends "shell" -> argv: mode, log, "shell"
    return fi.PersistentShell([sys.executable, str(script), mode, str(log)]), log


def test_commands_go_through_one_shell_in_order(tmp_path):
    sh, log = shell(tmp_path, "ok")
    assert sh.run("true") and sh.run("input tap 1 2; sleep 0.05; input tap 3 4") and sh.run("input tap 5 6")
    pid = sh.p.pid
    assert sh.run("true") and sh.p.pid == pid                      # reused, not one process per command
    sh.close()
    assert sh.p is None
    lines = log.read_bytes().split(b"\n")
    assert lines[1] == b"input tap 1 2; sleep 0.05; input tap 3 4; echo __fi2__"    # no \r\n from Windows text mode
    assert lines[2] == b"input tap 5 6; echo __fi3__"


def test_no_marker_in_time_is_a_timeout_and_the_shell_is_replaced(tmp_path):
    sh, _ = shell(tmp_path, "hang")
    t = time.monotonic()
    assert sh.run("input tap 1 2", timeout=0.5) is False
    assert 0.4 < time.monotonic() - t < 3 and sh.p is None         # killed: its late output can never be misread
    assert sh.run("true", timeout=0.3) is False                    # a fresh shell (still hanging) -> False again


def test_dead_shell_returns_false(tmp_path):
    sh, _ = shell(tmp_path, "dead")
    assert sh.run("true", timeout=3) is False and sh.p is None


def test_input_cmd_routes_through_the_shell_and_keeps_timeout_semantics(monkeypatch):
    sent, adb_calls = [], []
    monkeypatch.setattr(lp, "adb", lambda *a, **k: adb_calls.append(a))
    lp.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
    monkeypatch.setitem(lp.FAST, "shell", SimpleNamespace(run=lambda c, timeout=5: sent.append(c) or True))
    assert lp.input_cmd("input tap 1 2") and sent == ["input tap 1 2"] and not adb_calls
    monkeypatch.setitem(lp.FAST, "shell", SimpleNamespace(run=lambda c, timeout=5: False))
    assert lp.input_cmd("input tap 1 2") is False and lp.INPUTS["timed_out"]   # -> tap_timeout + nav pkill, as before
    assert lp.INPUTS["in_flight"] == 0
    lp.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)


# ---- play_match: the tap command and the new tap_timing fields ----------------------------------------------------
def rframe(tick):   # hand slot 0 cycles every 20 ticks -> plays get confirmed
    me = {"side": 0, "hand_deck_indices": [4 + tick // 20 % 4, 1, 2, 3], "elixir_raw": 80000, "deck_card_ids": [26000000] * 8,
          "deck_form_flags": [0] * 8}
    opp = dict(me, side=1, hand_deck_indices=[-1] * 4)
    return json.dumps({"battle_active": True, "coherent": True, "game_tick": tick, "sample_monotonic_us": tick * 50000,
                       "players": [me, opp], "entities": []}) + "\n"


class Pilot:
    def __init__(self):
        from pipeline.decision_options import DecisionOptions
        self.decision_options, self.match_seed, self.feature_version = DecisionOptions(), 0, 4

    def observe(self, f):
        return None

    def decide(self, f):
        return {"play": True, "card": 1, "form": 0, "hand_pos": 0, "deck_index": 0, "xy": (0.5, 0.6),
                "name": "Knight", "p_play": 0.9, "public_audit": {}}

    def record_play(self, *a):
        pass

    """One fake match (default frames: rframe, hand slot 0 cycling every 20 ticks); -> (adb shell commands, log events)."""
def play(monkeypatch, tmp_path, frames=None, pilot=None, pace=0.01, **extra):
    """One fake match (hand never rotates -> a play every CONFIRM_TICKS); -> (adb shell commands, log events)."""
    cmds = []

    def lines():
        for t, ln in frames or [(t, rframe(t)) for t in range(150, 330, 2)]:
            threading.Event().wait(pace)
            yield ln
    stream = lines()
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "adb", lambda *a, **k: cmds.append(a[-1]) or "")
    monkeypatch.setattr(lp.subprocess, "Popen", lambda *a, **k: SimpleNamespace(
        stdout=stream, stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0, terminate=lambda: None))
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    lp.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
    a = SimpleNamespace(tau=.35, leak=9.5, dry_run=False, ckpt="x", extrapolate=0, no_opp_counter=True,
                        ckpt_source="t", ckpt_sha256="t", public_audit=False, menu_guard=False, no_ability=True,
                        reader="v2", interval_ms=100, max_seconds=60, **extra)
    lp.play_match(a, pilot or Pilot(), lp.Layout(900, 1600), "cpu", None, record=False)
    ev = [json.loads(x) for x in next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()]
    return [c for c in cmds if "input tap" in c], ev


def test_default_tap_command_is_unchanged(monkeypatch, tmp_path):
    taps, ev = play(monkeypatch, tmp_path)           # no new attributes on the namespace: getattr defaults
    assert taps and all(c == "input tap 279 1424; sleep 0.05; input tap 450 791" for c in taps), taps
    start = ev[0]
    assert start["fast_input"] is False and start["tap_gap_ms"] == 50
    tt = [e for e in ev if e["event"] == "tap_timing"]
    assert tt and all(e["fast_input"] is False and e["recv_age_ms"] >= 0 and 0 <= e["sample_age_ms"] <= e["tap_end_ms"]
                      for e in tt), tt


def test_tap_gap_zero_drops_the_sleep(monkeypatch, tmp_path):
    taps, _ = play(monkeypatch, tmp_path, tap_gap_ms=0)
    assert taps and all(c == "input tap 279 1424; input tap 450 791" for c in taps), taps


@pytest.mark.parametrize("answers", [True, False])
def test_fast_input_match_uses_one_shell_and_closes_it(monkeypatch, tmp_path, answers):
    made = []

    class Shell:
        def __init__(self, adb, env=None):
            self.sent, self.closed = [], False
            made.append(self)

        def run(self, cmd, timeout=5.0):
            self.sent.append(cmd)
            return answers

        def close(self):
            self.closed = True
    monkeypatch.setattr(fi, "PersistentShell", Shell)
    taps, ev = play(monkeypatch, tmp_path, fast_input=True)
    assert len(made) == 1 and made[0].sent[0] == "true" and lp.FAST["shell"] is None
    if answers:      # every tap through the shell, none through adb.exe; closed at match end
        assert made[0].closed and not taps and len(made[0].sent) > 1
        assert all(e["fast_input"] for e in ev if e["event"] == "tap_timing")
    else:            # the warm-up got no answer: fall back to adb.exe per tap for the whole match
        assert made[0].sent == ["true"] and taps
        assert any(e["event"] == "fast_input_unavailable" for e in ev)
