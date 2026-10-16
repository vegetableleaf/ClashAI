"""--capture-p2 (parity data, owner 10-16) and the parallel-instance guard. Fakes only: no adb, no device, no sampler.
The capture's device command / binary live in a local-only helper; the wiring tests use a fake helper module."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, rframe  # noqa: E402


class FakeHelper:
    """Stands in for the local-only capture helper; ``fail`` = the step that breaks."""
    def __init__(self, fail=None, frames=b'{"tick":150}\n{"tick":152}\n'):
        self.fail, self.frames = fail, frames

    def push_and_verify(self, adb):
        adb("push", "bin", "dev_bin")
        if self.fail == "prepare":
            raise RuntimeError("device binary sha mismatch")
        return "ab" * 32

    def start_cmd(self, rva, ctx, side, tag, interval_ms=100):
        return f"P2START side={side} tag={tag} every={interval_ms}"

    def stop_cmd(self, tag):
        return f"P2STOP {tag}"

    def pull(self, adb, tag, out_dir, timeout=300):
        adb("pull", tag, out_dir)
        if self.fail == "pull":
            raise OSError("adb pull failed")
        os.makedirs(out_dir, exist_ok=True)
        frames = os.path.join(out_dir, "frames.jsonl")
        Path(frames).write_bytes(self.frames)
        return frames, len(self.frames)


def match(monkeypatch, tmp_path, cap=None, popen_fail=False):
    """One fake match; -> (ordered record of every adb / Popen call and stream end, log events)."""
    order = []

    def lines():
        for t in range(150, 330, 2):
            threading.Event().wait(0.01)
            yield rframe(t)
        order.append(("stream_end",))
    stream = lines()

    def popen(argv, **k):
        if "P2START" in argv[-1]:
            order.append(("p2_popen", argv[-1]))
            if popen_fail:
                raise OSError("adb.exe missing")
            return SimpleNamespace(poll=lambda: 0, terminate=lambda: None)
        order.append(("reader_popen",))
        return SimpleNamespace(stdout=stream, stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0,
                               terminate=lambda: None)
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "P2_DIR", tmp_path / "p2")
    monkeypatch.setattr(lp, "adb", lambda *a, **k: order.append(("adb",) + a) or "")
    monkeypatch.setattr(lp.subprocess, "Popen", popen)
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    if cap is not None:
        cap.adb = lambda *a, **k: order.append(("p2_adb",) + a) or ("gone" if "P2STOP" in a[-1] else "")
    lp.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
    a = SimpleNamespace(tau=.35, leak=9.5, dry_run=False, ckpt="x", extrapolate=0, no_opp_counter=True, ckpt_source="t",
                        ckpt_sha256="t", public_audit=True, menu_guard=False, no_ability=True, reader="v2",
                        interval_ms=100, max_seconds=60, p2=cap)
    lp.play_match(a, Pilot(), lp.Layout(900, 1600), "cpu", None, record=False)
    ev = [json.loads(x) for x in next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()]
    return order, ev


def play_view(order, ev):
    """What play did: every input command, every decision and play (timing fields excluded)."""
    taps = [o[-1] for o in order if o[0] == "adb" and "input tap" in o[-1]]
    dec = [(e["tick"], json.dumps(e["decision"], sort_keys=True)) for e in ev if e["event"] == "decision"]
    plays = [(e["tick"], e["name"], e["tap_hand"], e["tap_board"]) for e in ev if e["event"] == "play"]
    return taps, dec, plays


def captured(monkeypatch, tmp_path, helper, **kw):
    return match(monkeypatch, tmp_path, cap=lp.P2Capture(adb_fn=lambda *a, **k: "", mod=helper), **kw)


def test_capture_on_play_identical_one_start_command_pull_after_match(monkeypatch, tmp_path):
    (tmp_path / "off").mkdir()
    (tmp_path / "on").mkdir()
    order_off, ev_off = match(monkeypatch, tmp_path / "off")
    order_on, ev_on = captured(monkeypatch, tmp_path / "on", FakeHelper())
    assert play_view(order_on, ev_on) == play_view(order_off, ev_off) and play_view(order_off, ev_off)[0]
    assert not any(e["event"].startswith("p2") or "capture_p2" in e for e in ev_off)
    assert ev_on[0]["capture_p2"] is True

    # during the match (reader start -> the end-of-match pkill): the ONE start command, no other capture traffic
    r0 = order_on.index(("reader_popen",))
    kill = next(i for i, o in enumerate(order_on) if o[0] == "adb" and o[-1] == "pkill -f live_sampler")
    during = [o for o in order_on[r0:kill] if o[0] != "stream_end" and not (o[0] == "adb" and "input tap" in o[-1])]
    assert [o[0] for o in during if o[0] != "reader_popen"] == ["p2_popen"]   # reader restarts on stream end, as live
    assert during[1][0] == "p2_popen" and during[1][1].startswith("P2START side=0 tag=") and "every=100" in during[1][1]
    after = [o[0:2] for o in order_on[kill + 1:] if o[0] == "p2_adb"]
    assert after == [("p2_adb", "shell"), ("p2_adb", "pull")]        # stop by exact PID, then pull: both after pkill

    p2 = [e for e in ev_on if e["event"] == "p2_capture"]
    assert len(p2) == 1 and p2[0]["ok"] and p2[0]["frames"] == 2 and p2[0]["side"] == 0 and p2[0]["start_tick"] == 150
    assert [e["event"] for e in ev_on][-2:] == ["p2_capture", "end"]
    stem = Path(next((tmp_path / "on").glob("live_play_*.jsonl")).name).stem
    out = tmp_path / "on" / "p2" / stem
    run = json.loads((out / "run.json").read_text())
    assert p2[0]["dir"] == str(out) and run["live_log"] == stem + ".jsonl" and run["binary_sha256"] == "ab" * 32
    assert run["frames"] == 2 and len(run["frames_sha256"]) == 64 and run["observer_side"] == 0


@pytest.mark.parametrize("fail, why", [("prepare", "prepare:"), ("spawn", "start:"), ("pull", "adb pull failed"),
                                       ("empty", "missing or empty")])
def test_capture_failures_are_one_event_and_play_goes_on(monkeypatch, tmp_path, fail, why):
    (tmp_path / "off").mkdir()
    (tmp_path / "on").mkdir()
    order_off, ev_off = match(monkeypatch, tmp_path / "off")
    helper = FakeHelper(fail=fail if fail in ("prepare", "pull") else None, frames=b"" if fail == "empty" else b"{}\n")
    order_on, ev_on = captured(monkeypatch, tmp_path / "on", helper, popen_fail=fail == "spawn")
    assert play_view(order_on, ev_on) == play_view(order_off, ev_off)
    p2 = [e for e in ev_on if e["event"] == "p2_capture"]
    assert len(p2) == 1 and p2[0]["ok"] is False and why in p2[0]["why"], p2
    assert ev_on[-1]["event"] == "end" and not any(e["event"] == "stop" and "p2" in str(e) for e in ev_on)
    assert any(o[0] == "p2_popen" for o in order_on) == (fail != "prepare")   # no helper: nothing is started


def test_capture_never_started_without_a_side_frame():
    cap = lp.P2Capture(adb_fn=lambda *a, **k: "", mod=FakeHelper())
    cap.begin("x")
    rec = cap.finish(Path("live_play_x.jsonl"))
    assert rec["ok"] is False and "not started" in rec["why"]


def test_capture_p2_deployable_from_live_options(tmp_path):
    import argparse
    from pipeline.live_options import EXTRA_LIVE_FLAGS, add_live_options_arguments, parse_with_live_options
    assert ("--capture-p2", dict(action="store_true")) in EXTRA_LIVE_FLAGS
    f = tmp_path / "LIVE_OPTIONS"
    f.write_text("--log-frames --capture-p2\n")
    for path, want in ((f, True), (tmp_path / "missing", False)):
        ap = argparse.ArgumentParser()
        from pipeline.decision_options import add_arguments
        add_arguments(ap)
        for flag, kw in EXTRA_LIVE_FLAGS:
            ap.add_argument(flag, **kw)
        add_live_options_arguments(ap, path)
        assert parse_with_live_options(ap, [])[0].capture_p2 is want


# ---- the local-only helper itself (skipped where it is absent, e.g. a fresh clone) ------------------------------------
def helper_module():
    if not lp.P2_HELPER.is_file():
        pytest.skip("local-only phase-2 helper not present")
    import importlib.util
    spec = importlib.util.spec_from_file_location("p2_capture_real", lp.P2_HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_helper_command_and_per_match_files():
    h = helper_module()
    cmd = h.start_cmd("RVA_X", "CTX_Y", 1, "20261016_120000")
    out, err, pidf = h.dev_paths("20261016_120000")
    assert all(s in cmd for s in ("RVA_X", "CTX_Y", out, err, pidf)) and cmd.count("'") == 2
    assert "pidof" in cmd and "exit 3" in cmd                # one game process or no sampling at all
    assert pidf in h.stop_cmd("20261016_120000") and h.dev_paths("a")[0] != h.dev_paths("b")[0]


def test_helper_sha_checks(tmp_path):
    h = helper_module()
    b = tmp_path / "bin"
    b.write_bytes(b"binary")
    good = h.sha256_file(str(b))
    calls = []
    with pytest.raises(RuntimeError, match="local"):         # wrong local build: refused before any adb call
        h.push_and_verify(lambda *a, **k: calls.append(a) or "", local_bin=str(b), want="0" * 64)
    assert calls == []
    assert h.push_and_verify(lambda *a, **k: f"{good}  {h.DEV_BIN}\n", local_bin=str(b), want=good) == good
    with pytest.raises(RuntimeError, match="device"):
        h.push_and_verify(lambda *a, **k: "", local_bin=str(b), want=good)    # push failed / adb silent


# ---- parallel-instance guard ---------------------------------------------------------------------------------------
def test_other_live_plays_finds_only_other_instances():
    import psutil
    me = psutil.Process()
    parent = me.parents()[0].pid if me.parents() else -1
    P = lambda pid, name, *cmd: SimpleNamespace(info=dict(pid=pid, name=name, cmdline=list(cmd)))  # noqa: E731
    procs = [P(me.pid, "python.exe", "python", "live_play.py"),                      # this process
             P(parent, "python.exe", "python", "live_play.py"),                      # the venv launcher (our parent)
             P(901, "python.exe", "py", "C:/x/scratchpad/gauntlet/L68/live_reader/live_play.py", "--dry-run"),
             P(902, "python3.11", "py", "live_play_v2.py"),
             P(907, "python.exe", "py", "-u", "L72/hand_retention_integration/live_play_hand_v4.py", "--ladder"),
             P(908, "python.exe", "py", "overlay_replay.py", "live_play_20261016_120000.jsonl"),   # a log argument
             P(903, "bash.exe", "bash", "-c", "python live_play.py"),               # a shell wrapper, not an instance
             P(904, "python.exe", "py", "-m", "pytest", "test_capture_p2.py"),
             P(905, "python.exe", None),                                             # access denied: no cmdline
             P(906, None, None)]
    assert lp.other_live_plays(procs) == [901, 902, 907]


class Reached(Exception):
    pass


@pytest.mark.parametrize("extra, refused", [((), True), (("--allow-parallel",), False), (("--check",), False)])
def test_main_refuses_a_second_instance_unless_allowed(monkeypatch, capsys, extra, refused):
    import pipeline.live_checkpoint as lc
    monkeypatch.setattr(lp, "apply_reader_config", lambda strict=True: None)
    monkeypatch.setattr(lp, "other_live_plays", lambda: [4242])
    monkeypatch.setattr(lc, "resolve_checkpoint", lambda *a, **k: (_ for _ in ()).throw(Reached()))
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--no-live-options", "--dry-run", *extra])
    if refused:
        assert lp.main() == 2
        out = capsys.readouterr().out
        assert "refusing: another live_play is already running" in out and "[4242]" in out and "--allow-parallel" in out
    else:
        with pytest.raises(Reached):                         # went past the guard to the checkpoint selection
            lp.main()
