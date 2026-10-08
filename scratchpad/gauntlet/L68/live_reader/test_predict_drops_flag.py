"""--predict-drops: off by default (the pilot call and the start event are unchanged), on reaches GenPilot."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_play as lp


def _args(**kw):
    return SimpleNamespace(tau=.35, no_opp_counter=False, extrapolate=26, decision_seed=0, public_audit=False, device="cpu",
                           ckpt="/x/b.pt", **kw)


def test_load_pilot_passes_the_flag_only_when_set(monkeypatch):
    seen = []
    monkeypatch.setattr(lp, "GenPilot", lambda *a, **k: seen.append(k) or SimpleNamespace())
    lp.load_pilot(_args(), {})
    lp.load_pilot(_args(predict_drops=False), {})
    lp.load_pilot(_args(predict_drops=True), {})
    assert ["predict_drops" in k for k in seen] == [False, False, True] and seen[2]["predict_drops"] is True
    assert seen[0] == seen[1]                                    # default-off call is exactly today's call


def test_cli_flag_default_off_and_on(monkeypatch, tmp_path):
    got = []
    ck = tmp_path / "x.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(lp, "load_pilot", lambda args, cfg, ckpt=None: got.append(args.predict_drops) or ("cpu", SimpleNamespace(
        feature_version=5, decision_options=SimpleNamespace(), match_seed=0, reset_match=lambda: None)))
    monkeypatch.setattr(lp, "screen_size", lambda: (900, 1600))
    monkeypatch.setattr(lp, "wait_inputs_quiet", lambda: None)
    monkeypatch.setattr(lp, "play_match", lambda *a, **k: "battle_inactive")
    import ladder_nav
    monkeypatch.setattr(ladder_nav, "LadderNavRunner", lambda *x, **k: SimpleNamespace(probe=lambda: None, run=lambda: (True, "")))
    for extra, want in (([], False), (["--predict-drops"], True)):
        monkeypatch.setattr(sys, "argv", ["live_play.py", "--ladder", "--matches", "1", "--no-record", "--ckpt", str(ck), *extra])
        assert lp.main() == 0
        assert got[-1] is want


def test_start_event_key_only_when_on(monkeypatch, tmp_path):
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "adb", lambda *a, **k: "")
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    monkeypatch.setattr(lp.subprocess, "Popen", lambda *a, **k: SimpleNamespace(
        stdout=iter(()), stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0, terminate=lambda: None))
    pilot = SimpleNamespace(feature_version=5, decision_options=SimpleNamespace(), match_seed=0)
    starts = []
    for extra in ({}, {"predict_drops": True}):
        args = SimpleNamespace(tau=.35, leak=9.5, dry_run=True, ckpt="/x/b.pt", extrapolate=26, no_opp_counter=False,
                               ckpt_source="--ckpt", ckpt_sha256="b" * 64, public_audit=True, menu_guard=False,
                               no_ability=True, reader="v2", interval_ms=100, max_seconds=5, **extra)
        for old in tmp_path.glob("live_play_*.jsonl"):
            old.unlink()
        lp.play_match(args, pilot, SimpleNamespace(w=900, h=1600), "cpu", None, record=False)
        starts.append(json.loads(next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()[0]))
    assert "predict_drops" not in starts[0] and starts[1]["predict_drops"] is True


def test_flag_without_extrapolation_is_refused(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--predict-drops", "--extrapolate", "0"])
    assert lp.main() == 2 and "needs --extrapolate" in capsys.readouterr().out


def test_check_json_reports_predict_drops(monkeypatch, tmp_path, capsys):
    ck = tmp_path / "x.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(lp, "load_pilot", lambda args, cfg, ckpt=None: ("cpu", SimpleNamespace(
        feature_version=5, decision_options=SimpleNamespace())))
    seen = []
    for extra in ([], ["--predict-drops"]):
        monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--ckpt", str(ck), *extra])
        assert lp.main() == 0
        seen.append(json.loads(capsys.readouterr().out.strip().splitlines()[-1])["predict_drops"])
    assert seen == [False, True]
