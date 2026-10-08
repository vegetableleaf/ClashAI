"""--anti-leak: off by default (pilot untouched, logs say anti_leak False), on sets the SIM rule's parameters on the
pilot and in the start event / --check JSON; --no-anti-leak stays an accepted no-op."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_play as lp


def _args(**kw):
    return SimpleNamespace(tau=.35, no_opp_counter=False, extrapolate=26, decision_seed=0, public_audit=False,
                           device="cpu", ckpt="/x/b.pt", **kw)


def test_load_pilot_sets_the_rule_only_when_on(monkeypatch):
    monkeypatch.setattr(lp, "GenPilot", lambda *a, **k: SimpleNamespace())
    _, off = lp.load_pilot(_args(), {})
    _, off2 = lp.load_pilot(_args(anti_leak=False, anti_leak_elixir=9.0, anti_leak_seconds=12.0), {})
    _, on = lp.load_pilot(_args(anti_leak=True, anti_leak_elixir=9.0, anti_leak_seconds=12.0), {})
    assert not hasattr(off, "anti_leak_elixir") and not hasattr(off2, "anti_leak_elixir")
    assert (on.anti_leak_elixir, on.anti_leak_seconds) == (9.0, 12.0)


def _check(monkeypatch, tmp_path, capsys, extra):
    ck = tmp_path / "x.pt"
    ck.write_bytes(b"x")
    pilots = []

    def load(args, cfg, ckpt=None):
        p = SimpleNamespace(feature_version=5, decision_options=SimpleNamespace())
        if args.anti_leak:
            p.anti_leak_elixir, p.anti_leak_seconds = args.anti_leak_elixir, args.anti_leak_seconds
        pilots.append(p)
        return "cpu", p
    monkeypatch.setattr(lp, "load_pilot", load)
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--ckpt", str(ck), *extra])
    rc = lp.main()
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1]) if rc == 0 else None


@pytest.mark.parametrize("extra,want", [
    ([], dict(anti_leak=False, anti_leak_elixir=None, anti_leak_seconds=None)),
    (["--no-anti-leak"], dict(anti_leak=False, anti_leak_elixir=None, anti_leak_seconds=None)),
    (["--anti-leak"], dict(anti_leak=True, anti_leak_elixir=9.0, anti_leak_seconds=12.0)),
    (["--anti-leak", "--anti-leak-elixir", "10", "--anti-leak-seconds", "8"],
     dict(anti_leak=True, anti_leak_elixir=10.0, anti_leak_seconds=8.0))])
def test_check_json_carries_anti_leak(monkeypatch, tmp_path, capsys, extra, want):
    rc, out = _check(monkeypatch, tmp_path, capsys, extra)
    assert rc == 0 and {k: out[k] for k in want} == want


def test_anti_leak_and_no_anti_leak_together_are_refused(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit):
        _check(monkeypatch, tmp_path, capsys, ["--anti-leak", "--no-anti-leak"])


def test_start_event_carries_anti_leak(monkeypatch, tmp_path):
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "adb", lambda *a, **k: "")
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    monkeypatch.setattr(lp.subprocess, "Popen", lambda *a, **k: SimpleNamespace(
        stdout=iter(()), stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0, terminate=lambda: None))
    pilot = SimpleNamespace(feature_version=5, decision_options=SimpleNamespace(), match_seed=0)
    starts = []
    for extra in ({}, dict(anti_leak=True, anti_leak_elixir=9.0, anti_leak_seconds=12.0)):
        args = SimpleNamespace(tau=.35, leak=9.5, dry_run=True, ckpt="/x/b.pt", extrapolate=26, no_opp_counter=False,
                               ckpt_source="--ckpt", ckpt_sha256="b" * 64, public_audit=True, menu_guard=False,
                               no_ability=True, reader="v2", interval_ms=100, max_seconds=5, **extra)
        for old in tmp_path.glob("live_play_*.jsonl"):
            old.unlink()
        lp.play_match(args, pilot, SimpleNamespace(w=900, h=1600), "cpu", None, record=False)
        starts.append(json.loads(next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()[0]))
    assert (starts[0]["anti_leak"], starts[0]["anti_leak_elixir"], starts[0]["anti_leak_seconds"]) == (False, None, None)
    assert (starts[1]["anti_leak"], starts[1]["anti_leak_elixir"], starts[1]["anti_leak_seconds"]) == (True, 9.0, 12.0)
