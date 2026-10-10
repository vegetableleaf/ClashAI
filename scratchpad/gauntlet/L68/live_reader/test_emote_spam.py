"""--emote-spam (owner 2026-10-10): the scheduler rules and the live_play wiring (fake adb, no device)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emote_spam as es  # noqa: E402
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, play  # noqa: E402

EMOTE = "input tap 88 1365; sleep 0.15; input tap 710 1195"
CARD = "input tap 279 1424; sleep 0.05; input tap 450 791"


class WaitPilot(Pilot):
    """WAIT before tick `play_from`, a play from then on; p_play / gate_tau as given."""
    gate_tau = 0.35

    def __init__(self, play_from=10 ** 9, p_play=0.0):
        super().__init__()
        self.play_from, self.p_play = play_from, p_play

    def decide(self, f):
        if f["game_tick"] >= self.play_from:
            return super().decide(f)
        return {"play": False, "p_play": self.p_play, "gate_tau": self.gate_tau, "public_audit": {}}


def spam(monkeypatch, tmp_path, pilot, **kw):
    kw = dict(dict(emote_spam="on", emote_interval_s=0.3, emote_gap_ms=150, emote_guard=0.75), **kw)
    cmds, ev = play(monkeypatch, tmp_path, pilot=pilot, pace=0.02, tap_gap_ms=50, **kw)
    return cmds, ev


# ---- pure scheduler ----------------------------------------------------------------------------------------------
def test_due_only_on_wait_with_nothing_pending_after_the_interval():
    due = lambda **k: es.emote_due(**dict(dict(now=10.0, last_t=8.0, interval_s=1.35, play=False, busy=False,  # noqa: E731
                                              p_play=0.0, tau=0.35, guard=0.75), **k))
    assert due()
    assert not due(play=True)                         # a play decision never emotes
    assert not due(busy=True)                         # a follow-up / pending play / ability tap outstanding
    assert not due(now=9.3) and due(now=9.4)         # the interval, measured from the last first tap
    assert due(last_t=float("-inf"))


def test_guard_skips_a_near_play_and_zero_disables_it():
    due = lambda p, g: es.emote_due(10.0, 0.0, 1.35, False, False, p, 0.4, g)  # noqa: E731
    assert due(0.29, 0.75) and not due(0.31, 0.75) and not due(0.5, 0.75)   # p_play >= 0.75 x 0.4
    assert due(0.5, 0)


def test_hold_runs_from_the_first_tap_for_0_6_s():
    assert abs(es.hold_s(10.2, 10.0) - 0.4) < 1e-9 and es.hold_s(10.6, 10.0) == 0 and es.hold_s(11, 10.0) == 0
    assert es.hold_s(5.0, float("-inf")) == 0


def test_cmd_is_the_calibrated_two_taps_and_scales():
    assert es.emote_cmd(900, 1600, 150) == EMOTE
    assert es.emote_cmd(900, 1600, 0) == "input tap 88 1365; input tap 710 1195"
    assert es.emote_cmd(450, 800, 150) == "input tap 44 682; sleep 0.15; input tap 355 598"


# ---- play_match wiring ---------------------------------------------------------------------------------------------
def test_off_sends_nothing_and_logs_nothing_new(monkeypatch, tmp_path):
    cmds, ev = play(monkeypatch, tmp_path, pilot=WaitPilot(), pace=0.01)       # all WAIT, flag absent
    assert cmds == [] and not any(e["event"].startswith("emote") for e in ev)
    assert not any(k.startswith("emote") for e in ev for k in e)


def test_on_emotes_on_wait_at_the_interval(monkeypatch, tmp_path):
    cmds, ev = spam(monkeypatch, tmp_path, WaitPilot())
    n = sum(e["event"] == "emote" for e in ev)
    assert cmds == [EMOTE] * n and 2 <= n <= 7, (n, cmds)      # ~1.8 s of frames / 0.3 s, never faster
    e = next(e for e in ev if e["event"] == "emote")
    assert e["guard"] == 0.0 and e["tick"] >= 150
    assert next(e for e in ev if e["event"] == "start")["emote_spam"] == "on"
    end = next(e for e in ev if e["event"] == "end")
    assert end["emotes"] == n and end["emote_holds"] == 0


def test_guard_blocks_when_the_model_is_about_to_play(monkeypatch, tmp_path):
    cmds, _ = spam(monkeypatch, tmp_path, WaitPilot(p_play=0.3))              # 0.3 >= 0.75 x 0.35
    assert cmds == []
    (tmp_path / "b").mkdir()
    cmds, ev = spam(monkeypatch, tmp_path / "b", WaitPilot(p_play=0.3), emote_guard=0)
    assert cmds and next(e for e in ev if e["event"] == "emote")["guard"] == round(0.3 / 0.35, 3)


def test_a_play_right_after_an_emote_is_held(monkeypatch, tmp_path):
    cmds, ev = spam(monkeypatch, tmp_path, WaitPilot(play_from=156), emote_interval_s=5)
    assert cmds[0] == EMOTE and CARD in cmds                  # one emote, then the play on the same channel, in order
    assert cmds.index(CARD) > cmds.index(EMOTE)
    holds = [e for e in ev if e["event"] == "emote_hold"]
    assert holds and 0 < holds[0]["held_ms"] <= 600
    assert next(e for e in ev if e["event"] == "end")["emote_holds"] == len(holds)


def test_dry_run_logs_but_sends_nothing(monkeypatch, tmp_path):
    orig = lp.play_match
    monkeypatch.setattr(lp, "play_match", lambda a, *r, **k: (setattr(a, "dry_run", True), orig(a, *r, **k))[1])
    cmds, ev = spam(monkeypatch, tmp_path, WaitPilot())
    assert cmds == [] and any(e["event"] == "emote" and e.get("dry_run") for e in ev)


def test_check_passes_with_emote_spam_on(monkeypatch, tmp_path, capsys):
    ck = tmp_path / "m.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--ckpt", str(ck), "--emote-spam", "on"])
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4,
                                                                           decision_options=kw["decision_options"]))
    assert lp.main() == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["check"] == "LIVE_CHECK_PASS" and (out["emote_spam"], out["emote_interval_s"], out["emote_gap_ms"],
                                                 out["emote_guard"]) == ("on", 1.35, 150, 0.75)


def test_below_the_cooldown_is_refused(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--emote-spam", "on",
                                      "--emote-interval-s", "1.0"])
    assert lp.main() == 2 and "cooldown" in capsys.readouterr().out


def test_deployable_from_live_options(monkeypatch, tmp_path, capsys):
    from pipeline.live_options import EXTRA_LIVE_FLAGS
    flags = dict(EXTRA_LIVE_FLAGS)
    assert flags["--emote-spam"] == dict(choices=("off", "on"), default="off") and set(flags) >= {
        "--emote-interval-s", "--emote-gap-ms", "--emote-guard"}
    f, ck = tmp_path / "LIVE_OPTIONS", tmp_path / "m.pt"
    f.write_text("--emote-spam on\n--emote-gap-ms 120\n")
    ck.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--live-options-file", str(f), "--ckpt", str(ck)])
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4,
                                                                           decision_options=kw["decision_options"]))
    assert lp.main() == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (out["emote_spam"], out["emote_gap_ms"], out["emote_interval_s"], out["emote_guard"]) == ("on", 120, 1.35, 0.75)
