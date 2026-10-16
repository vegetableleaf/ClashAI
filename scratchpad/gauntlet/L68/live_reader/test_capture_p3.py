"""--capture-p3 (phase-3 probe beside the reader). Fakes only: no adb, no device, no probe.
Unlike phase 2, the probe survives the match's `pkill -f live_sampler`; the fake device models exactly that, so the
tests prove the capture itself stops it by exact PID after the match."""
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


class Device:
    """The probe's device-side life: started by the ONE start command, killed only by its own exact-PID stop."""
    def __init__(self):
        self.alive, self.started = False, 0

    def shell(self, cmd):
        if cmd == "pkill -f live_sampler":       # the reader's kill: the probe's name has no 'live_sampler'
            return ""
        if cmd.startswith("P3STOP"):
            was, self.alive = self.alive, False
            return "stopped" if was else "gone"
        return ""


class FakeHelper:
    """Stands in for the local-only p3_capture helper; ``fail`` = the step that breaks."""
    def __init__(self, fail=None, frames=b'{"game_tick":150}\n{"game_tick":152}\n'):
        self.fail, self.frames = fail, frames

    def push_and_verify(self, adb):
        adb("push", "bin", "dev_bin")
        if self.fail == "prepare":
            raise RuntimeError("device binary sha mismatch")
        return "cd" * 32

    def start_cmd(self, rva, ctx, side, tag, interval_ms=100):
        return f"P3START side={side} tag={tag} every={interval_ms}"

    def stop_cmd(self, tag):
        return f"P3STOP {tag}"

    def pull(self, adb, tag, out_dir, timeout=300):
        adb("pull", tag, out_dir)
        if self.fail == "pull":
            raise OSError("adb pull failed")
        os.makedirs(out_dir, exist_ok=True)
        frames = os.path.join(out_dir, "frames.jsonl")
        Path(frames).write_bytes(self.frames)
        return frames, len(self.frames)


def match(monkeypatch, tmp_path, cap=None, popen_fail=False, dev=None):
    """One fake match; -> (ordered record of every adb / Popen call, log events)."""
    order, dev = [], dev or Device()

    def lines():
        for t in range(150, 330, 2):
            threading.Event().wait(0.01)
            yield rframe(t)
    stream = lines()

    def popen(argv, **k):
        if "P3START" in argv[-1]:
            order.append(("p3_popen", argv[-1]))
            if popen_fail:
                raise OSError("adb.exe missing")
            dev.alive, dev.started = True, dev.started + 1
            return SimpleNamespace(poll=lambda: 0, terminate=lambda: None)
        order.append(("reader_popen",))
        return SimpleNamespace(stdout=stream, stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0,
                               terminate=lambda: None)

    def live_adb(*a, **k):
        order.append(("adb",) + a)
        return dev.shell(a[-1]) if a[0] == "shell" else ""
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "P3_DIR", tmp_path / "p3")
    monkeypatch.setattr(lp, "P2_DIR", tmp_path / "p2")
    monkeypatch.setattr(lp, "adb", live_adb)
    monkeypatch.setattr(lp.subprocess, "Popen", popen)
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    if cap is not None:
        cap.adb = lambda *a, **k: order.append(("p3_adb",) + a) or (dev.shell(a[-1]) if a[0] == "shell" else "")
    lp.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
    a = SimpleNamespace(tau=.35, leak=9.5, dry_run=False, ckpt="x", extrapolate=0, no_opp_counter=True, ckpt_source="t",
                        ckpt_sha256="t", public_audit=True, menu_guard=False, no_ability=True, reader="v2",
                        interval_ms=100, max_seconds=60, p2=cap)
    lp.play_match(a, Pilot(), lp.Layout(900, 1600), "cpu", None, record=False)
    ev = [json.loads(x) for x in next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()]
    return order, ev, dev


def play_view(order, ev):
    taps = [o[-1] for o in order if o[0] == "adb" and "input tap" in o[-1]]
    dec = [(e["tick"], json.dumps(e["decision"], sort_keys=True)) for e in ev if e["event"] == "decision"]
    plays = [(e["tick"], e["name"], e["tap_hand"], e["tap_board"]) for e in ev if e["event"] == "play"]
    return taps, dec, plays


def p3cap(helper):
    return lp.P3Capture(adb_fn=lambda *a, **k: "", mod=helper)


def test_p3_play_identical_probe_stopped_by_pid_after_match_then_pulled(monkeypatch, tmp_path):
    (tmp_path / "off").mkdir()
    (tmp_path / "on").mkdir()
    order_off, ev_off, _ = match(monkeypatch, tmp_path / "off")
    order_on, ev_on, dev = match(monkeypatch, tmp_path / "on", cap=p3cap(FakeHelper()))
    assert play_view(order_on, ev_on) == play_view(order_off, ev_off) and play_view(order_off, ev_off)[0]
    assert ev_on[0]["capture_p3"] is True and "capture_p2" not in ev_on[0]
    assert not any("capture" in e["event"] or "capture_p3" in e for e in ev_off)

    # one start command during the match; the probe outlives the reader's pkill; the capture's exact-PID stop ends it
    starts = [o for o in order_on if o[0] == "p3_popen"]
    assert len(starts) == 1 and starts[0][1].startswith("P3START side=0 tag=") and dev.started == 1
    kill = next(i for i, o in enumerate(order_on) if o[0] == "adb" and o[-1] == "pkill -f live_sampler")
    assert order_on.index(starts[0]) < kill
    after = [o[0:2] + ((o[2].split()[0],) if o[1] == "shell" else ()) for o in order_on[kill + 1:] if o[0] == "p3_adb"]
    assert after == [("p3_adb", "shell", "P3STOP"), ("p3_adb", "pull")]
    assert not dev.alive

    rec = [e for e in ev_on if e["event"] == "p3_capture"]
    assert len(rec) == 1 and rec[0]["ok"] and rec[0]["stopped"] == "stopped" and rec[0]["frames"] == 2
    assert [e["event"] for e in ev_on][-2:] == ["p3_capture", "end"]
    stem = next((tmp_path / "on").glob("live_play_*.jsonl")).stem
    out = tmp_path / "on" / "p3" / stem
    run = json.loads((out / "run.json").read_text())
    assert rec[0]["dir"] == str(out) and run["binary_sha256"] == "cd" * 32 and run["live_log"] == stem + ".jsonl"
    assert not (tmp_path / "on" / "p2").exists()


@pytest.mark.parametrize("fail, why", [("prepare", "prepare:"), ("spawn", "start:"), ("pull", "adb pull failed"),
                                       ("empty", "missing or empty")])
def test_p3_failures_are_one_event_play_goes_on_and_probe_never_left_running(monkeypatch, tmp_path, fail, why):
    (tmp_path / "off").mkdir()
    (tmp_path / "on").mkdir()
    order_off, ev_off, _ = match(monkeypatch, tmp_path / "off")
    helper = FakeHelper(fail=fail if fail in ("prepare", "pull") else None, frames=b"" if fail == "empty" else b"{}\n")
    order_on, ev_on, dev = match(monkeypatch, tmp_path / "on", cap=p3cap(helper), popen_fail=fail == "spawn")
    assert play_view(order_on, ev_on) == play_view(order_off, ev_off)
    rec = [e for e in ev_on if e["event"] == "p3_capture"]
    assert len(rec) == 1 and rec[0]["ok"] is False and why in rec[0]["why"], rec
    assert ev_on[-1]["event"] == "end" and not dev.alive


def test_p3_slow_start_is_still_stopped(monkeypatch, tmp_path):
    """The start thread outlives finish()'s 10 s join (proc not set yet): the exact-PID stop is still sent."""
    dev = Device()
    dev.alive = True
    sent = []
    cap = lp.P3Capture(adb_fn=lambda *a, **k: sent.append(a) or dev.shell(a[-1]), mod=FakeHelper())
    cap.begin("t1")
    cap.side, cap.tick = 0, 150
    cap.thread = SimpleNamespace(join=lambda timeout=None: None)    # proc stays None, err None
    rec = cap.finish(Path("live_play_x.jsonl"))
    assert rec["ok"] is False and "start:" in rec["why"] and not dev.alive and sent[1:] == [("shell", "P3STOP t1")]


def test_p3_supersedes_p2_and_is_deployable_from_live_options(tmp_path):
    import argparse
    from pipeline.decision_options import add_arguments
    from pipeline.live_options import EXTRA_LIVE_FLAGS, add_live_options_arguments, parse_with_live_options
    assert ("--capture-p3", dict(action="store_true")) in EXTRA_LIVE_FLAGS
    f = tmp_path / "LIVE_OPTIONS"
    f.write_text("--log-frames --capture-p3\n")
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    for flag, kw in EXTRA_LIVE_FLAGS:
        ap.add_argument(flag, **kw)
    add_live_options_arguments(ap, f)
    a = parse_with_live_options(ap, [])[0]
    assert a.capture_p3 is True and a.capture_p2 is False
    assert lp.P3Capture.paths(None) == (lp.P3_HELPER, lp.P3_DIR) and lp.P2Capture.paths(None) == (lp.P2_HELPER, lp.P2_DIR)


class Reached(Exception):
    pass


@pytest.mark.parametrize("extra, refused", [((), True), (("--allow-parallel",), False)])
def test_second_instance_guard_with_capture_p3(monkeypatch, capsys, extra, refused):
    import pipeline.live_checkpoint as lc
    monkeypatch.setattr(lp, "apply_reader_config", lambda strict=True: None)
    monkeypatch.setattr(lp, "other_live_plays", lambda: [4242])
    monkeypatch.setattr(lc, "resolve_checkpoint", lambda *a, **k: (_ for _ in ()).throw(Reached()))
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--no-live-options", "--dry-run", "--capture-p3", *extra])
    if refused:
        assert lp.main() == 2
        assert "refusing: another live_play is already running" in capsys.readouterr().out
    else:
        with pytest.raises(Reached):
            lp.main()


# ---- the local-only helper itself (skipped where it is absent, e.g. a fresh clone) ------------------------------------
def helper_module():
    if not lp.P3_HELPER.is_file():
        pytest.skip("local-only phase-3 helper not present")
    import importlib.util
    spec = importlib.util.spec_from_file_location("p3_capture_real", lp.P3_HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_helper_command_stop_by_pid_and_pinned_sha(tmp_path):
    h = helper_module()
    cmd = h.start_cmd("RVA_X", "CTX_Y", 1, "20261016_120000")
    out, err, pidf = h.dev_paths("20261016_120000")
    assert all(s in cmd for s in ("RVA_X", "CTX_Y", out, err, pidf, "exit 3")) and cmd.count("'") == 2
    stop = h.stop_cmd("20261016_120000")
    assert pidf in stop and os.path.basename(h.DEV_BIN) in stop and "kill $p" in stop and "pkill" not in stop
    assert "live_sampler" not in h.DEV_BIN                   # why the reader's pkill cannot stop it
    assert len(h.BIN_SHA256) == 64 and h.dev_paths("a")[0] != h.dev_paths("b")[0]
    if os.path.isfile(h.LOCAL_BIN):
        assert h.sha256_file(h.LOCAL_BIN) == h.BIN_SHA256
    b = tmp_path / "bin"
    b.write_bytes(b"binary")
    good, calls = h.sha256_file(str(b)), []
    with pytest.raises(RuntimeError, match="local"):
        h.push_and_verify(lambda *a, **k: calls.append(a) or "", local_bin=str(b), want="0" * 64)
    assert calls == []
    assert h.push_and_verify(lambda *a, **k: f"{good}  {h.DEV_BIN}\n", local_bin=str(b), want=good) == good
    with pytest.raises(RuntimeError, match="device"):
        h.push_and_verify(lambda *a, **k: "", local_bin=str(b), want=good)


def test_manual_runner_shares_the_helper():
    h = helper_module()
    runner = lp.P3_HELPER.parent / "run_p3.py"
    if not runner.is_file():
        pytest.skip("local-only run_p3.py not present")
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_p3_real", runner)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.BIN_SHA256 == h.BIN_SHA256 and mod.start_cmd("R", "C", 0, "t", 7) == h.start_cmd("R", "C", 0, "t", 7)
